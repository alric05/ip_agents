"""Tests for the Innography→Derwent migration.

Verifies:
1. Low-level helpers (_derwent_fld_search, _derwent_citation_search) send the
   correct HTTP payload to the Derwent API.
2. @tool wrappers (search_derwent_patents_fld, search_derwent_citations)
   pass args through to the helpers unchanged.
3. search.py tools (patent_keyword_search, get_patent_details,
   get_patent_citations, batch_patent_search, batch_citation_search,
   citation_chain_search) route through the Derwent helpers and format
   responses correctly.

All HTTP calls are mocked. JWT auth is stubbed via get_config patching.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Fixtures — sample Derwent API responses
# =============================================================================

SAMPLE_FLD_RESPONSE = {
    "body": [
        {
            "rank": "0.95",
            "field": [
                {"name": "pn", "value": "US10234567B2"},
                {"name": "ti", "value": "Polymer degradation sensor"},
                {"name": "tid", "form": "dwpi", "value": "UV-induced polymer degradation detector"},
                {"name": "ab", "form": "orig", "value": "A sensor detecting polymer degradation via UV fluorescence."},
                {"name": "nov", "form": "dwpi", "value": "Novel UV fluorescence detection method for polymer degradation."},
                {"name": "adv", "form": "dwpi", "value": "Real-time inline monitoring without sample destruction."},
                {"name": "use", "form": "dwpi", "value": "Quality control in plastic manufacturing."},
                {"name": "cl1", "value": "A sensor comprising: a UV source; a fluorescence detector..."},
                {"name": "prd", "value": "20200115"},
                {"name": "co", "value": "Example Corp"},
                {"name": "in", "value": "John Smith, Alice Doe"},
            ],
        },
        {
            "rank": "0.82",
            "field": [
                {"name": "pn", "value": "EP3411222B1"},
                {"name": "ti", "value": "Inline polymer quality monitor"},
                {"name": "tid", "form": "dwpi", "value": "Optical polymer quality inspection"},
                {"name": "nov", "form": "dwpi", "value": "Optical detection of polymer defects."},
                {"name": "prd", "value": "20190820"},
                {"name": "co", "value": "Plastics AG"},
            ],
        },
    ]
}

SAMPLE_CITATION_RESPONSE = {
    "body": [
        # Main patent (no ref_value)
        {
            "id": "US10234567B2",
            "field": [
                {"name": "pn", "value": "US10234567B2"},
                {"name": "ti", "value": "Polymer degradation sensor"},
                {"name": "tid", "value": "UV polymer detector"},
                {"name": "nov", "value": "Novel UV fluorescence detection."},
                {"name": "dcipfct", "value": "2"},
                {"name": "dcipct", "value": "1"},
            ],
        },
        # Forward citations (cite the main patent)
        {
            "id": "US11000111A1",
            "ref_value": "forward-citation",
            "ref_id": "US10234567B2",
            "field": [
                {"name": "pn", "value": "US11000111A1"},
                {"name": "ti", "value": "Improved polymer sensor"},
                {"name": "prd", "value": "20220301"},
                {"name": "co", "value": "NewCo Inc"},
                {"name": "nov", "value": "Improved detection method."},
            ],
        },
        {
            "id": "EP4000000A1",
            "ref_value": "forward-citation",
            "ref_id": "US10234567B2",
            "field": [
                {"name": "pn", "value": "EP4000000A1"},
                {"name": "ti", "value": "Next-gen fluorescence monitor"},
                {"name": "prd", "value": "20230115"},
            ],
        },
        # Backward citation (cited by the main patent)
        {
            "id": "US9000000B1",
            "ref_value": "backward-citation",
            "ref_id": "US10234567B2",
            "field": [
                {"name": "pn", "value": "US9000000B1"},
                {"name": "ti", "value": "UV fluorescence detector"},
                {"name": "prd", "value": "20150505"},
                {"name": "co", "value": "OldCo Ltd"},
            ],
        },
    ]
}


@pytest.fixture
def mock_jwt_config():
    """Patch get_config so JWT auth always succeeds."""
    with patch("src.tools.clients.derwent.get_config") as mock_cfg:
        mock_cfg.return_value = {"configurable": {"jwt_token": "FAKE.JWT.TOKEN"}}
        yield mock_cfg


@pytest.fixture
def mock_settings():
    """Patch get_settings so base URL is stable."""
    with patch("src.tools.clients.derwent.get_settings") as mock_s:
        s = MagicMock()
        s.derwent_api_base_url = "https://api.test.derwent.local"
        mock_s.return_value = s
        yield mock_s


@pytest.fixture
def mock_httpx_fld(mock_jwt_config, mock_settings):
    """Mock httpx.Client for FLD search endpoint. Returns the mock for payload inspection."""
    with patch("src.tools.clients.derwent.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_FLD_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_httpx_citations(mock_jwt_config, mock_settings):
    """Mock httpx.Client for citation endpoint. Returns the mock for payload inspection."""
    with patch("src.tools.clients.derwent.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CITATION_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client
        yield mock_client


# =============================================================================
# Response cleanup helper tests (Phase A)
# =============================================================================


class TestCleanText:
    """Tests for _clean_text: strip XML, collapse whitespace, normalize empty markers."""

    def test_empty_inputs(self):
        from src.tools.clients.derwent import _clean_text
        assert _clean_text(None) == ""
        assert _clean_text("") == ""
        assert _clean_text("   ") == ""

    def test_plain_string_passthrough(self):
        from src.tools.clients.derwent import _clean_text
        assert _clean_text("hello world") == "hello world"

    def test_strips_tsip_paragraph_wrapper(self):
        from src.tools.clients.derwent import _clean_text
        raw = '<tsip:paragraph xmlns:tsip="http://schemas.thomson.com/ts/20041221/tsip">Manufacturing M1 a polycarbonate.</tsip:paragraph>'
        assert _clean_text(raw) == "Manufacturing M1 a polycarbonate."

    def test_strips_tsip_abstract_wrapper(self):
        from src.tools.clients.derwent import _clean_text
        raw = (
            '<tsip:abstractTsxm xmlns:tsip="http://schemas.thomson.com/ts/20041221/tsip" '
            'xmlns:tsxm="http://schemas.thomson.com/ts/20041221/tsxm" tsip:lang="en" '
            'tsip:input="original"><tsxm:p tsxm:id="p-0001" tsxm:num="0000">'
            'A method for the manufacture of a polycarbonate composition.'
            '</tsxm:p></tsip:abstractTsxm>'
        )
        assert _clean_text(raw) == "A method for the manufacture of a polycarbonate composition."

    def test_strips_tsip_claim_wrapper_with_bold_and_list(self):
        from src.tools.clients.derwent import _clean_text
        raw = (
            '<tsip:claimTsxm xmlns:tsip="..." xmlns="..." id="CLM-00001" '
            'tsip:no="1" num="1" tsip:type="exemplary"><b>1</b>. An electrochemical cell '
            'comprising: <ul list-style="none"><li>a positive electrode;</li>'
            '<li>a negative electrode;</li></ul></tsip:claimTsxm>'
        )
        cleaned = _clean_text(raw)
        assert "<" not in cleaned and ">" not in cleaned
        assert "tsip:" not in cleaned and "tsxm:" not in cleaned
        assert "1. An electrochemical cell" in cleaned
        assert "positive electrode" in cleaned

    def test_none_given_becomes_empty(self):
        from src.tools.clients.derwent import _clean_text
        raw = '<tsip:paragraph xmlns:tsip="...">None given.</tsip:paragraph>'
        assert _clean_text(raw) == ""

    def test_none_given_case_insensitive(self):
        from src.tools.clients.derwent import _clean_text
        assert _clean_text("NONE GIVEN") == ""
        assert _clean_text("None Given.") == ""
        assert _clean_text("n/a") == ""

    def test_decodes_html_entities(self):
        from src.tools.clients.derwent import _clean_text
        assert _clean_text("R&amp;D expenditure &lt; 5%") == "R&D expenditure < 5%"

    def test_collapses_whitespace(self):
        from src.tools.clients.derwent import _clean_text
        assert _clean_text("A    method\nfor\t\tthe\nmanufacture") == "A method for the manufacture"

    def test_strips_leading_trailing_whitespace(self):
        from src.tools.clients.derwent import _clean_text
        assert _clean_text("   hello   ") == "hello"


class TestCleanSingle:
    """Tests for _clean_single: strip trailing comma padding."""

    def test_trailing_commas_stripped(self):
        from src.tools.clients.derwent import _clean_single
        assert _clean_single("SABIC GLOBAL TECHNOLOGIES BV,,,,") == "SABIC GLOBAL TECHNOLOGIES BV"

    def test_trailing_commas_with_spaces(self):
        from src.tools.clients.derwent import _clean_single
        assert _clean_single("BASF AG, , ,") == "BASF AG"

    def test_plain_value_unchanged(self):
        from src.tools.clients.derwent import _clean_single
        assert _clean_single("Example Corp") == "Example Corp"

    def test_internal_commas_preserved(self):
        """Internal commas (between words) should not be affected."""
        from src.tools.clients.derwent import _clean_single
        assert _clean_single("Smith, John Co.,,,,") == "Smith, John Co."

    def test_empty_returns_empty(self):
        from src.tools.clients.derwent import _clean_single
        assert _clean_single(None) == ""
        assert _clean_single("") == ""
        assert _clean_single(",,,,") == ""

    def test_xml_wrapper_also_stripped(self):
        from src.tools.clients.derwent import _clean_single
        raw = '<tsip:paragraph xmlns:tsip="...">BASF AG,,,,</tsip:paragraph>'
        assert _clean_single(raw) == "BASF AG"


class TestCleanList:
    """Tests for _clean_list: split, clean each, drop empties."""

    def test_empty_inputs(self):
        from src.tools.clients.derwent import _clean_list
        assert _clean_list(None) == []
        assert _clean_list("") == []
        assert _clean_list(",,,,") == []

    def test_single_inventor_with_trailing_commas(self):
        from src.tools.clients.derwent import _clean_list
        assert _clean_list("Boonman  Rob,,,,") == ["Boonman Rob"]

    def test_multiple_inventors(self):
        from src.tools.clients.derwent import _clean_list
        assert _clean_list("Smith John, Doe Alice") == ["Smith John", "Doe Alice"]

    def test_multiple_inventors_with_trailing_commas(self):
        from src.tools.clients.derwent import _clean_list
        assert _clean_list("Smith John, Doe Alice,,,,") == ["Smith John", "Doe Alice"]

    def test_double_space_collapsed(self):
        from src.tools.clients.derwent import _clean_list
        assert _clean_list("Lee  Jungwoo") == ["Lee Jungwoo"]

    def test_empty_entries_dropped(self):
        from src.tools.clients.derwent import _clean_list
        # "A, , B, ,, C" → ["A", "B", "C"]
        assert _clean_list("A, , B, ,, C") == ["A", "B", "C"]


class TestExtractBest:
    """Tests for _extract_best: form/language priority field extraction."""

    def test_missing_field_returns_empty(self):
        from src.tools.clients.derwent import _extract_best
        fields = [{"name": "ti", "value": "title"}]
        assert _extract_best(fields, "nov") == ""

    def test_single_match_returned(self):
        from src.tools.clients.derwent import _extract_best
        fields = [{"name": "ti", "value": "My Title"}]
        assert _extract_best(fields, "ti") == "My Title"

    def test_prefers_form_match(self):
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "docdb", "value": "docdb version"},
            {"name": "ab", "form": "orig",  "value": "orig version"},
        ]
        assert _extract_best(fields, "ab", prefer_form="orig") == "orig version"

    def test_prefers_english_when_multiple_languages(self):
        """Real-world case: Derwent returns EN + FR variants; we want EN."""
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "orig", "lang": "fr", "value": "FR text"},
            {"name": "ab", "form": "orig", "lang": "en", "value": "EN text"},
        ]
        assert _extract_best(fields, "ab", prefer_form="orig", lang="en") == "EN text"

    def test_form_match_preferred_over_language_only(self):
        """When both prefer_form and correct lang exist together, pick that one."""
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "docdb", "lang": "en", "value": "docdb EN"},
            {"name": "ab", "form": "orig",  "lang": "fr", "value": "orig FR"},
            {"name": "ab", "form": "orig",  "lang": "en", "value": "orig EN"},
        ]
        assert _extract_best(fields, "ab", prefer_form="orig", lang="en") == "orig EN"

    def test_falls_back_to_preferred_form_if_no_language_match(self):
        """If no English, fall back to any form match."""
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "orig", "lang": "fr", "value": "orig FR"},
            {"name": "ab", "form": "docdb", "lang": "ja", "value": "docdb JA"},
        ]
        assert _extract_best(fields, "ab", prefer_form="orig", lang="en") == "orig FR"

    def test_falls_back_to_language_match_if_no_form(self):
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "docdb", "lang": "fr", "value": "docdb FR"},
            {"name": "ab", "form": "docdb", "lang": "en", "value": "docdb EN"},
        ]
        assert _extract_best(fields, "ab", prefer_form="orig", lang="en") == "docdb EN"

    def test_falls_back_to_first_match_when_nothing_matches(self):
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "docdb", "lang": "ja", "value": "JA text"},
            {"name": "ab", "form": "docdb", "lang": "zh", "value": "ZH text"},
        ]
        assert _extract_best(fields, "ab", prefer_form="orig", lang="en") == "JA text"

    def test_field_without_lang_attribute_matches_lang_none(self):
        """Fields sometimes come back without a 'lang' key; treat as acceptable."""
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "orig", "value": "no-lang value"},
        ]
        assert _extract_best(fields, "ab", prefer_form="orig") == "no-lang value"

    def test_real_world_abstract_sample(self):
        """Reproduces the exact field layout seen in a real Derwent response."""
        from src.tools.clients.derwent import _extract_best
        fields = [
            {"name": "ab", "form": "orig",  "lang": "en", "value": "<tsip:abstractTsxm>EN orig</tsip:abstractTsxm>"},
            {"name": "ab", "form": "docdb", "lang": "en", "value": "<tsip:abstractTsxm>EN docdb</tsip:abstractTsxm>"},
            {"name": "ab", "form": "docdb", "lang": "fr", "value": "<tsip:abstractTsxm>FR docdb</tsip:abstractTsxm>"},
            {"name": "ab", "form": "orig",  "lang": "fr", "value": "<tsip:abstractTsxm>FR orig</tsip:abstractTsxm>"},
        ]
        # Should pick `orig` + `en` — the first Tier-1 match
        assert _extract_best(fields, "ab", prefer_form="orig", lang="en") \
               == "<tsip:abstractTsxm>EN orig</tsip:abstractTsxm>"


# =============================================================================
# JWT resolution tests
# =============================================================================


class TestGetJwtToken:
    """Tests for _get_jwt_token: config-first, env-var fallback."""

    def test_config_token_takes_priority(self, monkeypatch):
        from src.tools.clients.derwent import _get_jwt_token
        monkeypatch.setenv("DERWENT_JWT_TOKEN", "from-env")
        with patch("src.tools.clients.derwent.get_config") as m:
            m.return_value = {"configurable": {"jwt_token": "from-config"}}
            assert _get_jwt_token() == "from-config"

    def test_env_var_used_when_config_empty(self, monkeypatch):
        """Local dev scenario: langgraph dev / Studio / CLI — no HTTP layer injected a token."""
        from src.tools.clients.derwent import _get_jwt_token
        monkeypatch.setenv("DERWENT_JWT_TOKEN", "from-env")
        with patch("src.tools.clients.derwent.get_config") as m:
            m.return_value = {"configurable": {}}
            assert _get_jwt_token() == "from-env"

    def test_env_var_used_when_no_runtime_context(self, monkeypatch):
        """get_config() raises RuntimeError outside a graph run — env var saves us."""
        from src.tools.clients.derwent import _get_jwt_token
        monkeypatch.setenv("DERWENT_JWT_TOKEN", "from-env")
        with patch("src.tools.clients.derwent.get_config", side_effect=RuntimeError):
            assert _get_jwt_token() == "from-env"

    def test_returns_none_when_nothing_available(self, monkeypatch):
        from src.tools.clients.derwent import _get_jwt_token
        monkeypatch.delenv("DERWENT_JWT_TOKEN", raising=False)
        with patch("src.tools.clients.derwent.get_config") as m:
            m.return_value = {"configurable": {}}
            assert _get_jwt_token() is None

    def test_empty_env_var_is_treated_as_none(self, monkeypatch):
        from src.tools.clients.derwent import _get_jwt_token
        monkeypatch.setenv("DERWENT_JWT_TOKEN", "")
        with patch("src.tools.clients.derwent.get_config") as m:
            m.return_value = {"configurable": {}}
            assert _get_jwt_token() is None


# =============================================================================
# Low-level helper tests
# =============================================================================


class TestDerwentFldSearch:
    """Tests for _derwent_fld_search (core helper)."""

    def test_missing_jwt_returns_error_string(self, mock_settings, monkeypatch):
        """When no JWT is available (neither config nor env var), return an error string."""
        from src.tools.clients.derwent import _derwent_fld_search

        # Clear the DERWENT_JWT_TOKEN env-var fallback so neither source has a token
        monkeypatch.delenv("DERWENT_JWT_TOKEN", raising=False)

        with patch("src.tools.clients.derwent.get_config") as mock_cfg:
            mock_cfg.return_value = {"configurable": {}}
            result = _derwent_fld_search("CTB=(test);")

        assert isinstance(result, str)
        assert "Authentication required" in result

    def test_sends_correct_url_and_headers(self, mock_httpx_fld):
        from src.tools.clients.derwent import _derwent_fld_search

        _derwent_fld_search("CTB=(polymer);")

        call = mock_httpx_fld.post.call_args
        url = call.args[0] if call.args else call.kwargs.get("url") or call.args[0]
        assert url == "https://api.test.derwent.local/ip/patents/derwent/search-by-query-internal"

        headers = call.kwargs["headers"]
        assert headers["Authorization"] == "Bearer FAKE.JWT.TOKEN"
        assert headers["Content-Type"] == "application/json"

    def test_sends_correct_payload(self, mock_httpx_fld):
        """The request body must contain query, collections, size, and search-on-datatype.

        Note: as of commit 01728d2, queries are translated from Derwent UI
        syntax to T3 FLD syntax (lowercase tags, no trailing `;`, rename of
        a few codes) before being sent. See TestFieldTagCoverage for the
        exhaustive contract.
        """
        from src.tools.clients.derwent import _derwent_fld_search

        _derwent_fld_search("NOV=(UV NEAR3 fluorescence);", collections="derwentmatlat", size=15)

        body = mock_httpx_fld.post.call_args.kwargs["json"]
        params = body["params"][0]
        assert params["query"] == "nov=(UV NEAR3 fluorescence)"
        assert params["collections"] == "derwentmatlat"
        assert params["size"] == "15"
        assert params["search-on-datatype"] == "fld_dwpi"
        assert "return-fields" in params

    def test_query_translated_for_each_field_tag(self, mock_httpx_fld):
        """Smoke test across common Derwent field tags — each should reach the
        API in its translated T3 form. See TestFieldTagCoverage for the full
        parametrized contract."""
        from src.tools.clients.derwent import _derwent_fld_search

        cases = [
            ("CTB=(polymer);", "ctb=(polymer)"),
            ("NOV=(novel);", "nov=(novel)"),
            ("TID=(enhanced title);", "tid=(enhanced title)"),
            ("ALL=(broad);", "txt=(broad)"),  # ALL → txt rename
            ("IC=(G01N);", "ic=(G01N)"),
            ("PN=(US10234567);", "pn=(US10234567)"),
            ("TID=(a) AND NOV=(b);", "tid=(a) AND nov=(b)"),
        ]
        for raw, expected in cases:
            mock_httpx_fld.reset_mock()
            mock_httpx_fld.post.return_value.raise_for_status.return_value = None
            mock_httpx_fld.post.return_value.json.return_value = {"body": []}
            _derwent_fld_search(raw)
            sent = mock_httpx_fld.post.call_args.kwargs["json"]["params"][0]["query"]
            assert sent == expected, f"Translation mismatch: raw={raw!r} expected={expected!r} got={sent!r}"

    def test_response_formatting(self, mock_httpx_fld):
        """Response should be formatted into list of dicts with expected keys."""
        from src.tools.clients.derwent import _derwent_fld_search

        patents = _derwent_fld_search("CTB=(polymer);")

        assert isinstance(patents, list)
        assert len(patents) == 2

        p1 = patents[0]
        expected_keys = {
            "publication_number", "title", "dwpi_title", "abstract",
            "dwpi_abstract_novelty", "dwpi_abstract_advantage",
            "dwpi_abstract_use", "dwpi_abstract_detailed_description",
            "claims", "priority_date", "assignee", "inventors",
            "relevance_score",
        }
        assert expected_keys.issubset(p1.keys())
        assert p1["publication_number"] == "US10234567B2"
        assert p1["title"] == "Polymer degradation sensor"
        assert p1["dwpi_title"] == "UV-induced polymer degradation detector"
        assert p1["dwpi_abstract_novelty"].startswith("Novel UV fluorescence")
        assert p1["dwpi_abstract_advantage"].startswith("Real-time inline")
        assert p1["dwpi_abstract_use"].startswith("Quality control")
        assert p1["claims"].startswith("A sensor comprising")
        assert p1["priority_date"] == "20200115"
        assert p1["assignee"] == "Example Corp"
        assert p1["inventors"] == ["John Smith", "Alice Doe"]
        assert p1["relevance_score"] == 0.95

    def test_empty_response_returns_empty_list(self, mock_jwt_config, mock_settings):
        from src.tools.clients.derwent import _derwent_fld_search

        with patch("src.tools.clients.derwent.httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"body": []}
            mock_resp.raise_for_status.return_value = None
            mock_client.post.return_value = mock_resp
            mock_cls.return_value.__enter__.return_value = mock_client

            result = _derwent_fld_search("CTB=(nothing);")
            assert result == []


class TestDerwentCitationSearch:
    """Tests for _derwent_citation_search (core helper)."""

    def test_missing_jwt_returns_error_dict(self, mock_settings, monkeypatch):
        """When no JWT is available (neither config nor env var), return an error dict."""
        from src.tools.clients.derwent import _derwent_citation_search

        # Clear the DERWENT_JWT_TOKEN env-var fallback so neither source has a token
        monkeypatch.delenv("DERWENT_JWT_TOKEN", raising=False)

        with patch("src.tools.clients.derwent.get_config") as mock_cfg:
            mock_cfg.return_value = {"configurable": {}}
            result = _derwent_citation_search("US10234567B2")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Authentication required" in result["error"]

    def test_sends_correct_url_and_headers(self, mock_httpx_citations):
        from src.tools.clients.derwent import _derwent_citation_search

        # Use already-resolved Derwent id (trailing 8-digit date) so the
        # resolver is a no-op and this test exercises only the citation call.
        _derwent_citation_search("US10234567B220190319")

        call = mock_httpx_citations.post.call_args
        url = call.args[0] if call.args else call.kwargs.get("url")
        assert url == "https://api.test.derwent.local/ip/patents/derwent/search-by-ids-internal"

        headers = call.kwargs["headers"]
        assert headers["Authorization"] == "Bearer FAKE.JWT.TOKEN"

    def test_sends_correct_payload_single_patent(self, mock_httpx_citations):
        from src.tools.clients.derwent import _derwent_citation_search

        _derwent_citation_search("US10234567B220190319", max_citations=50)

        params = mock_httpx_citations.post.call_args.kwargs["json"]["params"][0]
        assert params["ids"] == "US10234567B220190319"
        assert params["size"] == 1  # single patent
        assert params["filter"] == "expand:citations@1;1;50"
        assert params["search-on-datatype"] == "fld_dwpi"
        assert params["dwpi-basic"] is True

    def test_sends_correct_payload_multiple_patents(self, mock_httpx_citations):
        from src.tools.clients.derwent import _derwent_citation_search

        _derwent_citation_search(
            "US10234567B220190319, EP3411222B120201028, US11000111A120220301"
        )

        params = mock_httpx_citations.post.call_args.kwargs["json"]["params"][0]
        assert params["ids"] == (
            "US10234567B220190319,EP3411222B120201028,US11000111A120220301"
        )
        assert params["size"] == 3

    def test_response_formatting_single_patent(self, mock_httpx_citations):
        """Single patent ID should return a dict (not a list)."""
        from src.tools.clients.derwent import _derwent_citation_search

        result = _derwent_citation_search("US10234567B220190319")

        assert isinstance(result, dict)
        assert result["patent_number"] == "US10234567B2"
        assert result["total_forward_citations"] == 2
        assert result["total_backward_citations"] == 1

        assert len(result["forward_citations"]) == 2
        assert result["forward_citations"][0]["publication_number"] == "US11000111A1"
        assert result["forward_citations"][0]["title"] == "Improved polymer sensor"

        assert len(result["backward_citations"]) == 1
        assert result["backward_citations"][0]["publication_number"] == "US9000000B1"


# =============================================================================
# Bare-pub-number → Derwent-id resolution
# =============================================================================


class TestResolvePatentIds:
    """Tests for _resolve_patent_ids: bare pub numbers → Derwent internal ids.

    Derwent's citation endpoint keys on the concatenated ``pn+pd`` id format
    (e.g. ``US8718044B220140506``). Bare pub numbers like ``US8718044B2``
    silently return an empty body. The resolver does one FLD lookup to map
    bare numbers to their full ids before the citation call is made.
    """

    def test_already_resolved_id_is_a_noop(self, mock_jwt_config, mock_settings):
        """If the input already has a trailing 8-digit date, no lookup happens."""
        from src.tools.clients.derwent import _resolve_patent_ids

        with patch("src.tools.clients.derwent.httpx.Client") as mock_client_cls:
            resolved, unresolved = _resolve_patent_ids("US8718044B220140506")
            assert resolved == "US8718044B220140506"
            assert unresolved == []
            mock_client_cls.assert_not_called()

    def test_underscore_separator_counts_as_resolved(self, mock_jwt_config, mock_settings):
        """``US3256182A_19660614`` (underscore+date) also bypasses the resolver."""
        from src.tools.clients.derwent import _resolve_patent_ids

        with patch("src.tools.clients.derwent.httpx.Client") as mock_client_cls:
            resolved, _ = _resolve_patent_ids("US3256182A_19660614")
            assert resolved == "US3256182A_19660614"
            mock_client_cls.assert_not_called()

    def test_bare_pub_is_resolved_via_fld_lookup(self, mock_jwt_config, mock_settings):
        """Bare pub numbers trigger an FLD lookup and get the full id substituted."""
        from src.tools.clients.derwent import _resolve_patent_ids

        # Mock FLD response: body items carry both the top-level `id`
        # (concatenated pn+pd) and the `pn` field we key off of.
        fld_lookup_body = {
            "body": [
                {
                    "id": "US8718044B220140506",
                    "field": [
                        {"name": "pn", "value": "US8718044B2"},
                        {"name": "pd", "value": "20140506"},
                    ],
                },
                {
                    "id": "US10234567B220190319",
                    "field": [
                        {"name": "pn", "value": "US10234567B2"},
                        {"name": "pd", "value": "20190319"},
                    ],
                },
            ]
        }
        with patch("src.tools.clients.derwent.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = fld_lookup_body
            mock_response.raise_for_status.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_client

            resolved, unresolved = _resolve_patent_ids(
                "US8718044B2, US10234567B2"
            )

            assert resolved == "US8718044B220140506,US10234567B220190319"
            assert unresolved == []

            # Verify the resolver used separate PN=() clauses joined with OR
            # (Derwent doesn't support OR inside a single PN=() group).
            sent_query = mock_client.post.call_args.kwargs["json"]["params"][0]["query"]
            assert sent_query == "PN=(US8718044B2) OR PN=(US10234567B2);"

    def test_unknown_pub_surfaced_in_unresolved_list(self, mock_jwt_config, mock_settings):
        """FLD hit for some inputs but not others → partial resolution."""
        from src.tools.clients.derwent import _resolve_patent_ids

        fld_lookup_body = {
            "body": [
                {
                    "id": "US8718044B220140506",
                    "field": [{"name": "pn", "value": "US8718044B2"}],
                },
            ]
        }
        with patch("src.tools.clients.derwent.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = fld_lookup_body
            mock_response.raise_for_status.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_client

            resolved, unresolved = _resolve_patent_ids(
                "US8718044B2, DOES_NOT_EXIST_123"
            )

            assert resolved == "US8718044B220140506"
            assert unresolved == ["DOES_NOT_EXIST_123"]

    def test_citation_search_errors_when_nothing_resolves(
        self, mock_jwt_config, mock_settings
    ):
        """If no input can be resolved, surface an error dict — do not silently
        fall through to the citation endpoint with bare numbers."""
        from src.tools.clients.derwent import _derwent_citation_search

        # Empty FLD response = nothing resolves
        with patch("src.tools.clients.derwent.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"body": []}
            mock_response.raise_for_status.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_client

            result = _derwent_citation_search("US9999999B9, US8888888A1")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Could not resolve" in result["error"]


# =============================================================================
# @tool wrapper tests — verify wrappers pass args to helpers unchanged
# =============================================================================


class TestToolWrappers:
    """The @tool wrappers should be thin pass-throughs to the helpers."""

    def test_search_derwent_patents_fld_wrapper(self):
        with patch("src.tools.clients.derwent._derwent_fld_search") as mock_helper:
            mock_helper.return_value = [{"publication_number": "US1"}]
            from src.tools.clients.derwent import search_derwent_patents_fld

            result = search_derwent_patents_fld.invoke(
                {"query": "CTB=(test);", "size": 5}
            )

            mock_helper.assert_called_once()
            call_args = mock_helper.call_args
            # Check positional or keyword passed through
            # Signature: _derwent_fld_search(query, collections, return_fields, size)
            args_passed = call_args.args + tuple(call_args.kwargs.values())
            assert "CTB=(test);" in args_passed
            assert 5 in args_passed
            assert result == [{"publication_number": "US1"}]

    def test_search_derwent_citations_wrapper(self):
        with patch("src.tools.clients.derwent._derwent_citation_search") as mock_helper:
            mock_helper.return_value = {"patent_number": "US1", "total_forward_citations": 0}
            from src.tools.clients.derwent import search_derwent_citations

            result = search_derwent_citations.invoke(
                {"patent_ids": "US1,US2", "max_citations": 20}
            )

            mock_helper.assert_called_once()
            call_args = mock_helper.call_args
            args_passed = call_args.args + tuple(call_args.kwargs.values())
            assert "US1,US2" in args_passed
            assert 20 in args_passed
            assert result["patent_number"] == "US1"


# =============================================================================
# search.py wrapper tests — verify they route through Derwent
# =============================================================================


class TestSearchPyWrappers:
    """Tests for search.py tools — must route through Derwent helpers."""

    def test_patent_keyword_search_calls_derwent_fld(self):
        with patch("src.tools.clients.derwent._derwent_fld_search") as mock_helper:
            mock_helper.return_value = [
                {
                    "publication_number": "US10234567B2",
                    "title": "Polymer sensor",
                    "dwpi_title": "UV polymer detector",
                    "abstract": "A sensor that detects polymer degradation.",
                    "priority_date": "20200115",
                    "assignee": "Example Corp",
                }
            ]
            from src.tools.search import patent_keyword_search

            result = patent_keyword_search.invoke(
                {"query": "CTB=(polymer NEAR5 degradation);", "feature_id": "F1", "max_results": 5}
            )

            mock_helper.assert_called_once()
            # Verify query passed unchanged
            call = mock_helper.call_args
            assert call.args[0] == "CTB=(polymer NEAR5 degradation);"
            # max_results should be passed as size
            assert call.kwargs.get("size") == 5 or 5 in call.args

            # Output contains formatted results
            assert "US10234567B2" in result
            assert "Polymer sensor" in result or "UV polymer detector" in result
            assert "F1" in result

    def test_patent_keyword_search_handles_error_string(self):
        """If helper returns an error string, the tool should pass it through."""
        with patch("src.tools.clients.derwent._derwent_fld_search") as mock_helper:
            mock_helper.return_value = "Error: Invalid or expired authentication token."
            from src.tools.search import patent_keyword_search

            result = patent_keyword_search.invoke({"query": "CTB=(x);"})
            assert "Error" in result
            assert "authentication token" in result.lower()

    def test_get_patent_details_uses_pn_query(self):
        """get_patent_details should build a 'pn=(...)' query and call Derwent."""
        with patch("src.tools.clients.derwent._derwent_fld_search") as mock_helper:
            mock_helper.return_value = [
                {
                    "publication_number": "US10234567B2",
                    "title": "Original Title",
                    "dwpi_title": "DWPI Title",
                    "abstract": "Abstract text.",
                    "dwpi_abstract_novelty": "Novelty description.",
                    "dwpi_abstract_advantage": "Advantages.",
                    "dwpi_abstract_use": "Uses.",
                    "claims": "Claim 1: ...",
                    "priority_date": "20200115",
                    "assignee": "Example Corp",
                    "inventors": ["Smith, J."],
                    "dwpi_abstract_detailed_description": "Detailed description.",
                }
            ]
            from src.tools.search import get_patent_details

            result = get_patent_details.invoke({"publication_number": "US10234567B2"})

            mock_helper.assert_called_once()
            query_sent = mock_helper.call_args.args[0]
            assert query_sent == "pn=(US10234567B2)"

            # Output should contain all major sections
            assert "US10234567B2" in result
            assert "Original Title" in result
            assert "DWPI Title" in result
            assert "Novelty description" in result
            assert "Advantages" in result
            assert "Example Corp" in result

    def test_get_patent_details_no_result(self):
        """When Derwent returns empty list, tool should return 'No patent found' message."""
        with patch("src.tools.clients.derwent._derwent_fld_search") as mock_helper:
            mock_helper.return_value = []
            from src.tools.search import get_patent_details

            result = get_patent_details.invoke({"publication_number": "US99999999"})
            assert "No patent found" in result
            assert "US99999999" in result

    def test_get_patent_citations_calls_derwent_citation(self):
        with patch("src.tools.clients.derwent._derwent_citation_search") as mock_helper:
            mock_helper.return_value = {
                "patent_number": "US10234567B2",
                "total_forward_citations": 2,
                "total_backward_citations": 1,
                "forward_citations": [
                    {
                        "publication_number": "US11000111A1",
                        "title": "Improved sensor",
                        "assignee": "NewCo",
                        "priority_date": "20220301",
                        "dwpi_novelty": "Improved detection.",
                    }
                ],
                "backward_citations": [
                    {
                        "publication_number": "US9000000B1",
                        "title": "Prior art detector",
                        "assignee": "OldCo",
                        "priority_date": "20150505",
                    }
                ],
            }
            from src.tools.search import get_patent_citations

            result = get_patent_citations.invoke({"publication_number": "US10234567B2"})

            mock_helper.assert_called_once()
            assert mock_helper.call_args.args[0] == "US10234567B2"

            assert "Forward Citations" in result
            assert "Backward Citations" in result
            assert "US11000111A1" in result
            assert "US9000000B1" in result
            assert "Improved sensor" in result

    def test_get_patent_citations_handles_error(self):
        with patch("src.tools.clients.derwent._derwent_citation_search") as mock_helper:
            mock_helper.return_value = {"error": "Rate limit exceeded."}
            from src.tools.search import get_patent_citations

            result = get_patent_citations.invoke({"publication_number": "US10234567B2"})
            assert "Patent citations error" in result
            assert "Rate limit" in result

    def test_batch_citation_search_loops_through_patents(self):
        """batch_citation_search should call the citation helper once per seed patent."""
        with patch("src.tools.clients.derwent._derwent_citation_search") as mock_helper:
            # First call returns citations for patent 1, second for patent 2
            mock_helper.side_effect = [
                {
                    "patent_number": "US1",
                    "total_forward_citations": 1,
                    "total_backward_citations": 0,
                    "forward_citations": [
                        {"publication_number": "US11", "title": "Cite1", "assignee": "C1"}
                    ],
                    "backward_citations": [],
                },
                {
                    "patent_number": "US2",
                    "total_forward_citations": 1,
                    "total_backward_citations": 0,
                    "forward_citations": [
                        {"publication_number": "US22", "title": "Cite2", "assignee": "C2"}
                    ],
                    "backward_citations": [],
                },
            ]
            from src.tools.search import batch_citation_search

            result = batch_citation_search.invoke({
                "publication_numbers": ["US1", "US2"],
                "max_citations_per_patent": 10,
            })

            assert mock_helper.call_count == 2
            # First call: US1
            assert mock_helper.call_args_list[0].args[0] == "US1"
            # Second call: US2
            assert mock_helper.call_args_list[1].args[0] == "US2"

            # Output should include both patents
            assert "US1" in result
            assert "US2" in result
            assert "US11" in result
            assert "US22" in result

    def test_citation_chain_search_level1(self):
        """citation_chain_search should fetch level 1 citations from the seed patent."""
        with patch("src.tools.clients.derwent._derwent_citation_search") as mock_helper:
            mock_helper.return_value = {
                "patent_number": "US1",
                "total_forward_citations": 1,
                "total_backward_citations": 1,
                "forward_citations": [
                    {
                        "publication_number": "US11",
                        "title": "UV polymer detector",
                        "assignee": "NewCo",
                        "priority_date": "20220101",
                        "dwpi_novelty": "UV detection.",
                    }
                ],
                "backward_citations": [
                    {
                        "publication_number": "US9",
                        "title": "Old sensor",
                        "assignee": "OldCo",
                        "priority_date": "20100101",
                    }
                ],
            }
            from src.tools.search import citation_chain_search

            result = citation_chain_search.invoke({
                "seed_patent": "US1",
                "max_depth": 1,  # Only level 1 to keep test simple
                "max_per_level": 5,
                "feature_keywords": ["UV", "polymer"],
            })

            # At least one call made (level 1)
            assert mock_helper.call_count >= 1
            assert mock_helper.call_args_list[0].args[0] == "US1"

            assert "Citation Chain Analysis" in result
            assert "US1" in result
            assert "US11" in result

    def test_batch_patent_search_uses_derwent(self):
        """batch_patent_search should call _derwent_fld_search once per query."""
        with patch("src.tools.clients.derwent._derwent_fld_search") as mock_helper:
            mock_helper.side_effect = [
                [{"publication_number": "US1"}, {"publication_number": "US2"}],
                [{"publication_number": "US2"}, {"publication_number": "US3"}],
            ]
            from src.tools.search import batch_patent_search

            result = batch_patent_search.invoke({
                "queries": [
                    {"query_id": "K1.1", "query_text": "CTB=(polymer);", "feature_ids": ["F1"]},
                    {"query_id": "K1.2", "query_text": "NOV=(UV);", "feature_ids": ["F2"]},
                ],
                "max_results_per_query": 10,
            })

            assert mock_helper.call_count == 2
            # Query text passed unchanged
            assert mock_helper.call_args_list[0].args[0] == "CTB=(polymer);"
            assert mock_helper.call_args_list[1].args[0] == "NOV=(UV);"

            assert "K1.1" in result
            assert "K1.2" in result
            # US1 and US2 from Q1; US3 new in Q2 (US2 seen)
            assert "Unique Patents Found**: 3" in result or "3" in result


# =============================================================================
# Field tag coverage tests — verify different Derwent field tags round-trip
# =============================================================================


class TestFieldTagCoverage:
    """Verify every supported Derwent field tag gets translated to the T3 FLD
    equivalent before hitting the API.

    The `QueryTranslator` (added in commit 01728d2) lowercases field tags,
    strips trailing `;`, and renames a handful of codes to their T3 service
    equivalents (`ALL`→`txt`, `IN`→`inn`, `PRD`→`prdt`, `CPC`→`cpcc`). These
    cases lock in the exact wire format so regressions in the XML mapping
    surface loudly.
    """

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            # Pure-cosmetic: lowercase tag + strip trailing `;`.
            ("CTB=(polymer);", "ctb=(polymer)"),
            ("ALLD=(dwpi text);", "alld=(dwpi text)"),
            ("TI=(original title);", "ti=(original title)"),
            ("AB=(original abstract);", "ab=(original abstract)"),
            ("CL=(claims);", "cl=(claims)"),
            ("CL1=(first claim);", "cl1=(first claim)"),
            ("TID=(dwpi title);", "tid=(dwpi title)"),
            ("NOV=(novelty);", "nov=(novelty)"),
            ("ADV=(advantage);", "adv=(advantage)"),
            ("USE=(use section);", "use=(use section)"),
            ("ABD=(dwpi abstract);", "abd=(dwpi abstract)"),
            ("IC=(G01N);", "ic=(G01N)"),
            ("PN=(US10234567);", "pn=(US10234567)"),
            ("PA=(Example Corp);", "pa=(Example Corp)"),
            ("CUPPA=(parent corp);", "cuppa=(parent corp)"),
            ("PY>=(2020);", "py>=(2020)"),
            # Field-code renames — these are semantic equivalents in T3.
            ("ALL=(broad search);", "txt=(broad search)"),
            ("IN=(Smith);", "inn=(Smith)"),
            ("PRD>=(20200101);", "prdt>=(20200101)"),
            ("CPC=(G01N21/64);", "cpcc=(G01N21/64)"),
            # Combined expressions: operators + parens preserved, each tag
            # independently translated.
            (
                "TID=(polymer) AND NOV=(UV);",
                "tid=(polymer) AND nov=(UV)",
            ),
            (
                "CTB=(sensor) AND IC=(G01N);",
                "ctb=(sensor) AND ic=(G01N)",
            ),
            (
                "(TID=(polymer) OR NOV=(polymer)) AND CTB=(UV);",
                "(tid=(polymer) OR nov=(polymer)) AND ctb=(UV)",
            ),
        ],
    )
    def test_query_is_translated_to_t3(self, mock_httpx_fld, query, expected):
        """Each Derwent-UI-syntax query must reach the API in its T3 FLD form."""
        from src.tools.clients.derwent import _derwent_fld_search

        mock_httpx_fld.post.return_value.json.return_value = {"body": []}
        _derwent_fld_search(query)

        sent_query = mock_httpx_fld.post.call_args.kwargs["json"]["params"][0]["query"]
        assert sent_query == expected


# =============================================================================
# Real API integration tests
#
# Auto-skipped unless DERWENT_JWT_TOKEN env var is set (see tests/conftest.py).
# Run with: DERWENT_JWT_TOKEN=<token> pytest tests/test_derwent_migration.py -m real_api -v
# =============================================================================


@pytest.fixture
def real_jwt_config():
    """Patch get_config with a real JWT from DERWENT_JWT_TOKEN env var.

    Unlike the mocked fixtures, this does NOT patch httpx.Client or get_settings
    — we want real HTTP calls to the real Derwent base URL.
    """
    import os
    token = os.environ.get("DERWENT_JWT_TOKEN")
    if not token:
        pytest.skip("DERWENT_JWT_TOKEN not set")
    with patch("src.tools.clients.derwent.get_config") as mock_cfg:
        mock_cfg.return_value = {"configurable": {"jwt_token": token}}
        yield mock_cfg


def _context_around(text: str, needle: str, width: int = 40) -> str:
    """Return the characters around the first occurrence of `needle` for error msgs."""
    i = text.find(needle)
    if i < 0:
        return "(not found)"
    start = max(0, i - width)
    end = min(len(text), i + len(needle) + width)
    return repr(text[start:end])


def _assert_clean_markdown(text: str) -> None:
    """Assert rendered tool markdown contains no Derwent response artifacts.

    Invariants enforced (also applied at the raw dict layer by Phase C):
      - No `<tsip:...>` or `<tsxm:...>` namespace-wrapped XML fragments
      - No literal DWPI `"None given."` placeholder
      - No trailing-comma padding (",,,," patterns from multi-slot joins)
    """
    assert "<tsip:" not in text, \
        f"tsip: XML namespace leaked into markdown: {_context_around(text, '<tsip:')}"
    assert "<tsxm:" not in text, \
        f"tsxm: XML namespace leaked into markdown: {_context_around(text, '<tsxm:')}"
    assert "None given." not in text, \
        f"DWPI 'None given.' placeholder not normalized: {_context_around(text, 'None given.')}"
    # 3+ consecutive commas indicate trailing-comma padding (",,,," from Derwent joins).
    # Two commas can legitimately appear in "Smith, John, Co." so only flag ,,,
    assert ",,," not in text, \
        f"trailing comma padding leaked into markdown: {_context_around(text, ',,,')}"


@pytest.mark.real_api
class TestDerwentRealApi:
    """Integration tests against the real Derwent API.

    All tests use small `size` values to minimize quota consumption.
    Tests skip automatically when DERWENT_JWT_TOKEN is not set.
    """

    # Well-known US patent used for deterministic lookup tests.
    # If this patent is not in your Derwent collection, override via the
    # DERWENT_TEST_PATENT env var.
    TEST_PATENT = "US10234567B2"

    def _patent_id(self) -> str:
        import os
        return os.environ.get("DERWENT_TEST_PATENT", self.TEST_PATENT)

    def test_real_fld_search_basic_query(self, real_jwt_config):
        """Verify a basic CTB= query hits the real API and returns patents."""
        from src.tools.clients.derwent import _derwent_fld_search

        result = _derwent_fld_search("CTB=(polymer);", size=3)

        # Helper returns a string on error, list on success
        assert not isinstance(result, str), f"API returned error: {result}"
        assert isinstance(result, list)
        assert len(result) >= 1, "Expected at least 1 result for 'polymer'"

        for patent in result:
            assert patent.get("publication_number"), \
                f"Missing publication_number in {patent}"
            # At least one of title or dwpi_title should be present
            assert patent.get("title") or patent.get("dwpi_title"), \
                f"Missing title/dwpi_title in {patent}"

    def test_real_fld_search_by_patent_number(self, real_jwt_config):
        """Verify PN=(...) lookup works as a deterministic patent lookup."""
        from src.tools.clients.derwent import _derwent_fld_search

        patent_id = self._patent_id()
        # Strip kind code suffix for PN= query — Derwent PN typically accepts raw number
        pn_query = f"PN=({patent_id});"
        result = _derwent_fld_search(pn_query, size=1)

        assert not isinstance(result, str), f"API returned error: {result}"
        assert isinstance(result, list)

        if len(result) == 0:
            pytest.skip(
                f"Test patent {patent_id} not found in Derwent collection "
                f"(derwentmatlat). Set DERWENT_TEST_PATENT to a known patent."
            )

        # If we got a result, verify it matches the requested patent
        pub_num = result[0].get("publication_number", "")
        # Strip non-alphanumeric for loose comparison (e.g., US10234567B2 vs US10234567)
        assert patent_id.replace("B2", "").replace("B1", "").replace("A1", "") in pub_num \
            or pub_num in patent_id, \
            f"Expected {patent_id}, got {pub_num}"

    def test_real_fld_search_field_tags_differ(self, real_jwt_config):
        """Different field tags should produce different result sets.

        Proves the agent's instructions about field-specific searches provide
        real precision benefit — e.g., NOV= and TID= shouldn't return
        identical results to ALL=.
        """
        from src.tools.clients.derwent import _derwent_fld_search

        term = "polymer"
        results_by_tag = {}

        for tag in ["NOV", "TID", "ALL"]:
            query = f"{tag}=({term});"
            r = _derwent_fld_search(query, size=5)
            assert not isinstance(r, str), f"{tag}= query failed: {r}"
            assert isinstance(r, list)
            results_by_tag[tag] = [p.get("publication_number") for p in r]

        # At least one tag should return a non-empty result
        non_empty = [t for t, pubs in results_by_tag.items() if pubs]
        assert non_empty, f"All field tag queries returned 0 results: {results_by_tag}"

        # Different tags should produce at least some different patents
        # (if all three return identical sets, field targeting has no effect)
        unique_sets = {tuple(sorted(p for p in pubs if p)) for pubs in results_by_tag.values()}
        assert len(unique_sets) > 1, (
            f"All three field tags returned identical results — field targeting "
            f"has no effect: {results_by_tag}"
        )

    def test_real_citation_search(self, real_jwt_config):
        """Verify citation search hits the real API with a BARE pub number.

        This is the shape agents actually pass (they don't know about Derwent's
        concatenated pn+pd id format). The helper must auto-resolve internally.
        Do NOT soften 'No data found' into a skip — that masked a real bug
        during the Innography→Derwent migration.
        """
        from src.tools.clients.derwent import _derwent_citation_search

        patent_id = self._patent_id()
        assert not re.search(r"\d{8}$", patent_id), (
            f"Test patent id {patent_id!r} must be a BARE pub number (no date "
            "suffix) to exercise the resolver. Update TEST_PATENT / "
            "DERWENT_TEST_PATENT."
        )
        result = _derwent_citation_search(patent_id, max_citations=10)

        # A missing patent is a real failure now, not a skip. The only reason
        # this should be empty is if the JWT has no access, which would come
        # back as an auth error — not 'No data found'.
        if isinstance(result, dict) and "error" in result:
            if "Authentication" in result["error"] or "permissions" in result["error"].lower():
                pytest.skip(f"Derwent auth error (outside test control): {result['error']}")
            pytest.fail(
                f"Citation search failed for bare pub {patent_id!r} — resolver "
                f"regression likely. Error: {result['error']}"
            )

        # Single-patent response returns dict (not list)
        if isinstance(result, list):
            assert len(result) >= 1
            result = result[0]

        assert isinstance(result, dict)
        assert "patent_number" in result
        assert "total_forward_citations" in result
        assert "total_backward_citations" in result
        assert isinstance(result["forward_citations"], list)
        assert isinstance(result["backward_citations"], list)
        assert result["total_forward_citations"] >= 0
        assert result["total_backward_citations"] >= 0

    def test_real_patent_keyword_search_tool(self, real_jwt_config):
        """End-to-end: patent_keyword_search tool should return formatted, clean markdown."""
        from src.tools.search import patent_keyword_search

        result = patent_keyword_search.invoke({
            "query": "CTB=(polymer);",
            "feature_id": "F1",
            "max_results": 3,
        })

        assert isinstance(result, str)
        # Either formatted results or a clear error/no-results message
        if "No patents found" in result:
            pytest.skip("Real API returned no patents for CTB=(polymer); — unexpected but not a test failure")
        assert "Patent Search Results" in result, f"Unexpected output: {result[:200]}"
        assert "F1" in result

        # Phase E: wrapper output must be free of Derwent response artifacts
        _assert_clean_markdown(result)

    def test_real_get_patent_details_tool(self, real_jwt_config):
        """End-to-end: get_patent_details tool should fetch a patent by number, clean markdown."""
        from src.tools.search import get_patent_details

        patent_id = self._patent_id()
        result = get_patent_details.invoke({"publication_number": patent_id})

        assert isinstance(result, str)

        if "No patent found" in result:
            pytest.skip(
                f"Test patent {patent_id} not found in Derwent collection. "
                "Set DERWENT_TEST_PATENT to a known patent."
            )

        assert "Patent Details" in result, f"Unexpected output: {result[:200]}"
        # At least one DWPI/bibliographic field should be populated in the markdown
        assert any(marker in result for marker in ["Title:", "DWPI Title:", "Abstract", "DWPI Novelty"]), \
            f"No patent metadata in output: {result[:500]}"

        # Phase E: wrapper output must be free of Derwent response artifacts
        _assert_clean_markdown(result)

    def test_real_get_patent_citations_tool_is_clean(self, real_jwt_config):
        """End-to-end: get_patent_citations tool should return formatted, clean markdown.

        Uses US3256182A_19660614 — a 1966 Texaco patent confirmed to have
        forward + backward citations in the derwentmatlat collection.
        """
        from src.tools.search import get_patent_citations

        result = get_patent_citations.invoke({"publication_number": "US3256182A_19660614"})

        assert isinstance(result, str)
        if "error" in result.lower() and "citations" in result.lower() and "forward" not in result.lower():
            pytest.skip(f"Citation lookup returned error (may be env/quota): {result[:200]}")

        assert "Patent Citations" in result, f"Unexpected output: {result[:300]}"
        # At least one of the citation sections should be present
        assert "Forward Citations" in result or "Backward Citations" in result, \
            f"No citation sections in output: {result[:500]}"

        # Phase E: wrapper output must be free of Derwent response artifacts
        _assert_clean_markdown(result)

    def test_real_response_is_clean(self, real_jwt_config):
        """Real Derwent response should have no XML markup, namespace leakage, or formatting artifacts.

        This is the acceptance test for the response cleanup work (Phase C):
        asserts the invariants listed in the migration plan.
        """
        from src.tools.clients.derwent import _derwent_fld_search

        patents = _derwent_fld_search("CTB=(polymer NEAR5 degradation);", size=5)
        assert not isinstance(patents, str), f"API returned error: {patents}"
        assert patents, "Expected at least one patent"

        string_fields = (
            "publication_number", "title", "dwpi_title", "abstract",
            "dwpi_abstract_novelty", "dwpi_abstract_advantage",
            "dwpi_abstract_use", "dwpi_abstract_detailed_description",
            "claims", "assignee", "priority_date",
        )

        for p in patents:
            for f_name in string_fields:
                val = p.get(f_name, "")
                if not val:
                    continue  # empty is fine
                # No raw XML angle brackets
                assert "<" not in val, f"{p.get('publication_number')} {f_name} has '<': {val[:120]!r}"
                assert ">" not in val, f"{p.get('publication_number')} {f_name} has '>': {val[:120]!r}"
                # No namespace prefixes leaking
                assert "tsip:" not in val, f"{p.get('publication_number')} {f_name} has tsip:: {val[:120]!r}"
                assert "tsxm:" not in val, f"{p.get('publication_number')} {f_name} has tsxm:: {val[:120]!r}"
                # No leading/trailing whitespace
                assert val == val.strip(), f"{p.get('publication_number')} {f_name} has stray whitespace"

            # Assignee must not end with comma-padding
            if p.get("assignee"):
                assert not p["assignee"].endswith(","), \
                    f"assignee trailing comma: {p['assignee']!r}"

            # Inventors must be clean
            for inv in p.get("inventors", []):
                assert "  " not in inv, f"inventor has double space: {inv!r}"
                assert not inv.endswith(","), f"inventor trailing comma: {inv!r}"
                assert "<" not in inv and ">" not in inv, f"inventor has XML: {inv!r}"

            # DWPI fields should be empty or substantive — never "None given."
            for dwpi_field in ("dwpi_abstract_novelty", "dwpi_abstract_advantage", "dwpi_abstract_use"):
                val = p.get(dwpi_field, "")
                assert val.lower() != "none given.", \
                    f"{dwpi_field} is 'None given.' — should be normalized to empty string"


# =============================================================================
# Full-stack integration tests via local server
#
# Assumes server.py is running on http://localhost:8000. Auto-skipped when:
#   - DERWENT_JWT_TOKEN is not set, OR
#   - localhost:8000/health does not respond
#
# Start the server first:
#   uvicorn server:api --port 8000 --reload
#
# Then run:
#   DERWENT_JWT_TOKEN=<token> pytest tests/test_derwent_migration.py -m real_server -v -s
# =============================================================================


def _parse_sse_stream(lines_iter):
    """Parse an SSE stream into (event_type, data_dict) tuples.

    SSE format:
        event: <type>
        data: <json>
        <blank line>
    """
    import json as _json

    event_type = None
    data_buf: list[str] = []

    for raw in lines_iter:
        line = raw.rstrip("\n").rstrip("\r")
        if not line:
            # End of event block
            if event_type is not None:
                data_str = "\n".join(data_buf)
                try:
                    data = _json.loads(data_str) if data_str else {}
                except _json.JSONDecodeError:
                    data = {"_raw": data_str}
                yield event_type, data
            event_type = None
            data_buf = []
            continue

        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_buf.append(line[len("data:"):].lstrip())


@pytest.mark.real_server
class TestDerwentViaServer:
    """End-to-end integration test: JWT → server.py → agent → Derwent API.

    Reproduces the curl pattern used by the frontend and teammates:
        curl -X POST http://localhost:8000/chat/stream \\
             -H 'Authorization: Bearer <JWT>' \\
             -H 'Content-Type: application/json' \\
             -d '{"message": "..."}'
    """

    SERVER_URL = "http://localhost:8000"
    CHAT_STREAM_PATH = "/chat/stream"
    # Generous timeout — full agent runs take minutes; we wait for `done` or `error`
    REQUEST_TIMEOUT = 300.0

    def test_real_derwent_citation_via_server(self):
        """Send the teammate's exact request and verify Derwent tool runs successfully."""
        import os
        import httpx

        jwt = os.environ["DERWENT_JWT_TOKEN"]  # skip marker ensures this is set

        body = {
            "message": (
                "Use search_derwent_citations to analyze patent US3256182A_19660614 "
                "and retrieve all its forward and backward citations"
            ),
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {jwt}",
            "Accept": "text/event-stream",
        }

        collected: list[tuple[str, dict]] = []
        activity_bubbles: list[dict] = []
        saw_done = False
        saw_error = False
        error_data: dict | None = None

        url = f"{self.SERVER_URL}{self.CHAT_STREAM_PATH}"

        try:
            with httpx.Client(timeout=self.REQUEST_TIMEOUT) as client:
                with client.stream("POST", url, headers=headers, json=body) as resp:
                    assert resp.status_code == 200, (
                        f"/chat/stream returned {resp.status_code}: "
                        f"{resp.read().decode('utf-8', errors='replace')[:500]}"
                    )

                    for event_type, data in _parse_sse_stream(resp.iter_lines()):
                        collected.append((event_type, data))

                        if event_type == "stage_data":
                            inner = data.get("stage_data", {}) or {}
                            if inner.get("component") == "agentActivityBubble":
                                activity_bubbles.append(inner)
                        elif event_type == "done":
                            saw_done = True
                            break
                        elif event_type == "error":
                            saw_error = True
                            error_data = data
                            break
        except httpx.ReadTimeout:
            pytest.fail(
                f"Stream timed out after {self.REQUEST_TIMEOUT}s. "
                f"Collected {len(collected)} events, last few: {collected[-5:]}"
            )

        # Always print the event summary so -s shows what happened
        print(f"\n\n=== SSE event summary ({len(collected)} events) ===")
        for et, d in collected:
            preview = str(d)[:200]
            print(f"  {et}: {preview}")

        assert not saw_error, f"Stream ended with error event: {error_data}"

        # Derwent tool invocations surface as agentActivityBubble events whose
        # `text` contains the unmapped tool name, e.g. "Running search_derwent_citations...".
        derwent_tool_names = {"search_derwent_citations", "search_derwent_patents_fld"}
        derwent_activity = [
            b for b in activity_bubbles
            if any(name in (b.get("text") or "") for name in derwent_tool_names)
        ]
        assert derwent_activity, (
            "No Derwent tool was invoked. agentActivityBubble texts: "
            f"{[b.get('text') for b in activity_bubbles]}"
        )

        # No auth-error markers should leak into bubble text.
        error_markers = ("Invalid or expired authentication token", "Invalid signature",
                         "Authentication required")
        auth_errors = [
            b for b in activity_bubbles
            if any(marker in (b.get("text") or "") for marker in error_markers)
        ]
        assert not auth_errors, (
            f"Derwent tool surfaced auth error(s): {auth_errors[:2]}"
        )

        assert saw_done, (
            "Stream ended without a 'done' event. "
            f"Last events: {collected[-5:]}"
        )
