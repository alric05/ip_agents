#!/usr/bin/env python3
"""
Derwent to T3 FLD Query Translator
================================
Translates Derwent field codes to T3 FLD search codes for middleware usage.

This module provides a query translation service that:
- Loads field mappings from XML configuration
- Parses Derwent fielded queries
- Translates field codes to T3 service codes
- Returns T3-compatible query strings

Usage:
    from query_translator import QueryTranslator
    
    translator = QueryTranslator()
    t3_query = translator.translate("ti=solar AND pn=US*")
    # Returns: ti=solar AND pn=US*
    
    # Get field metadata
    metadata = translator.get_field_metadata("ti")
    # Returns: {'derwent_code': 'ti', 'search_code': 'ti', 'phrase_search': 'ti=', ...}
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


class FieldMapping:
    """Represents a single field mapping from Derwent to T3."""
    
    def __init__(self, name: str, search_code: str = "", phrase_search: str = "",
                 retrieve_code: str = "", record_view_code: str = "", sort_code: str = "",
                 database: str = ""):
        self.name = name  # Derwent field code
        self.search_code = search_code  # T3 search code
        self.phrase_search = phrase_search  # Query syntax pattern
        self.retrieve_code = retrieve_code  # Result extraction codes
        self.record_view_code = record_view_code  # Display codes
        self.sort_code = sort_code  # Sort capability
        self.database = database  # Source database name
    
    def to_dict(self) -> Dict[str, str]:
        """Convert mapping to dictionary."""
        return {
            'derwent_code': self.name,
            'search_code': self.search_code,
            'phrase_search': self.phrase_search,
            'retrieve_code': self.retrieve_code,
            'record_view_code': self.record_view_code,
            'sort_code': self.sort_code,
            'database': self.database,
            'is_sortable': bool(self.sort_code),
            'has_fallback': ',' in self.retrieve_code if self.retrieve_code else False,
        }
    
    def __repr__(self) -> str:
        return f"FieldMapping(name='{self.name}', search_code='{self.search_code}')"


class XMLFieldConfigLoader:
    """Loads field mappings from XML configuration file."""
    
    def __init__(self, xml_path: str):
        """
        Initialize loader with XML file path.
        
        Args:
            xml_path: Path to XML configuration file
            
        Raises:
            FileNotFoundError: If XML file not found
            ET.ParseError: If XML is malformed
        """
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"XML configuration file not found: {xml_path}")
        
        self.xml_path = xml_path
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
    
    def load_fld_fields(self) -> Dict[str, FieldMapping]:
        """
        Load all field mappings from T3 datasource databases (INTEGRATED, FLD, DWPI, IPAFIELDS).
        
        Priority order (first match wins):
        1. INTEGRATED - Complete/combined field set (most comprehensive)
        2. FLD - Standard fields (baseline)
        3. DWPI - Chemistry/specific fields (fallback)
        4. IPAFIELDS - IPA-specific fields (final fallback)
        
        Only loads from T3 datasource. Does NOT load from T3A or T3FAST.
        
        If the same field code appears in multiple databases, the one from the highest priority
        database is used.
        
        Returns:
            Dictionary mapping Derwent field codes to FieldMapping objects
            
        Raises:
            ValueError: If T3 datasource section not found
        """
        fields = {}
        
        # Database load order (INTEGRATED has highest priority)
        database_priority = ['INTEGRATED', 'FLD', 'DWPI', 'IPAFIELDS']
        
        # Navigate to T3 datasource only (not T3A, T3FAST, etc.)
        for datasource in self.root.findall('.//datasource'):
            # Check if this is the T3 datasource (name can be attribute or child element)
            ds_name = datasource.get('name')
            if ds_name is None:
                # Try child element
                name_elem = datasource.find('name')
                ds_name = name_elem.text if name_elem is not None else None
            
            # Only process T3 datasource (skip T3A, T3FAST, etc.)
            if ds_name != 'T3':
                continue
            
            # Load all databases in priority order
            # First match wins - if field exists in INTEGRATED, skip same field in FLD/DWPI/etc.
            for db_name in database_priority:
                databases = datasource.findall(f'databases/database[@name="{db_name}"]')
                
                for database in databases:
                    # Extract all field mappings
                    for field_elem in database.findall('fields/field'):
                        field_name = field_elem.get('name', '').lower()  # Normalize to lowercase
                        if not field_name:
                            continue
                        
                        # Only add if not already present (respects priority order)
                        # This means INTEGRATED fields take precedence over FLD, etc.
                        if field_name not in fields:
                            mapping = FieldMapping(
                                name=field_name,  # Store as lowercase
                                search_code=field_elem.get('searchCode', ''),
                                phrase_search=field_elem.get('phraseSearch', ''),
                                retrieve_code=field_elem.get('retrieveCode', ''),
                                record_view_code=field_elem.get('recordViewCode', ''),
                                sort_code=field_elem.get('sortCode', ''),
                                database=db_name  # Store database name
                            )
                            fields[field_name] = mapping
            
            return fields
        
        raise ValueError("T3 datasource section not found in XML configuration")
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get metadata about the configuration."""
        fields = self.load_fld_fields()
        return {
            'file_path': self.xml_path,
            'file_size_bytes': os.path.getsize(self.xml_path),
            'total_fields': len(fields),
            'sortable_fields': sum(1 for f in fields.values() if f.sort_code),
            'fields_with_fallback': sum(1 for f in fields.values() if ',' in (f.retrieve_code or '')),
        }


class QueryTokenizer:
    """Tokenizes Derwent FLD queries into field expressions and operators."""
    
    # Updated regex pattern to support comma-separated field codes
    # Matches: single field code OR multiple field codes separated by commas
    # Examples: "ti", "ti,cl", "ti, cl, nov" all match
    # Actual value extraction is handled by _extract_field_value()
    FIELD_PATTERN = re.compile(
        r'(\w+(?:\s*,\s*\w+)*)\s*(<=|>=|<>|=|<|>)',  # Field code(s) and operator
        re.IGNORECASE
    )
    
    # All supported boolean operators in Derwent FLD
    # Basic boolean operators
    BASIC_OPERATORS = {'AND', 'OR', 'NOT'}
    
    # Proximity operators (within-field term proximity)
    # ADJ [n] = Adjacent (0-99 word distance)
    # NEAR [n] = Near (0-99 word distance, any order)
    # SAME = Same sentence
    # WITH = Same paragraph/field
    PROXIMITY_OPERATORS = {'ADJ', 'NEAR', 'SAME', 'WITH'}
    
    # Negated proximity operators (patent content only)
    NEGATED_PROXIMITY_OPERATORS = {'NOT_ADJ', 'NOT_NEAR', 'NOT_SAME', 'NOT_WITH'}
    
    # Combined set of all operators
    OPERATORS = BASIC_OPERATORS | PROXIMITY_OPERATORS | NEGATED_PROXIMITY_OPERATORS
    
    @staticmethod
    def _extract_field_value(query: str, start_pos: int, operator: str) -> str:
        """
        Extract a complete field value starting after the operator.
        Handles quoted strings, parenthesized expressions with nesting, etc.
        
        Returns the extracted value string.
        """
        i = start_pos
        value_chars = []
        paren_depth = 0
        in_quotes = False
        quote_char = None
        
        while i < len(query):
            ch = query[i]
            
            # Handle quotes
            if ch in ('"', "'") and (i == 0 or query[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = ch
                elif ch == quote_char:
                    in_quotes = False
            
            # Stop if not in quotes and hit end markers
            if not in_quotes:
                # Check for end of value - look for top-level BOOLEAN operator or end marker
                # NOTE: Proximity operators (ADJ, NEAR, SAME, WITH, NOT_ADJ, NOT_NEAR, NOT_SAME, NOT_WITH)
                # are NOT terminators - they work within the field and should be included in the value
                if paren_depth == 0:
                    # Check if we're at a top-level BOOLEAN operator word
                    if ch.isspace() or ch in (';', ','):
                        # Look ahead to check for operator
                        remaining = query[i:].lstrip()
                        if remaining and not remaining[0].isalnum():
                            break
                        # Only break on BOOLEAN operators, not proximity operators
                        if remaining:
                            next_word = remaining.split()[0].upper()
                            if next_word in QueryTokenizer.BASIC_OPERATORS:
                                break
                        # Not a terminator - append character and continue
                        if ch.isspace():
                            value_chars.append(ch)
                            i += 1
                            continue
                        else:
                            break
                
                # Track parenthesis depth
                if ch == '(':
                    paren_depth += 1
                elif ch == ')':
                    paren_depth -= 1
                    if paren_depth < 0:
                        # Extra close paren - end of value
                        break
            
            value_chars.append(ch)
            i += 1
        
        return ''.join(value_chars).rstrip()
    
    @staticmethod
    def tokenize(query: str) -> List[Tuple[str, str]]:
        """
        Tokenize query into (token_type, token_value) pairs using improved parsing
        that handles complex nested expressions.
        
        Token types: 'field', 'operator', 'paren'
        
        Args:
            query: Derwent FLD query string
            
        Returns:
            List of (token_type, token_value) tuples
        """
        tokens = []
        query = query.strip()
        i = 0
        
        while i < len(query):
            # Skip whitespace and terminators
            if query[i].isspace() or query[i] == ';':
                i += 1
                continue
            
            # Try to match field expression with improved value extraction
            # Supports comma-separated field codes: ti,cl,nov=value
            field_match = re.match(r'(\w+(?:\s*,\s*\w+)*)\s*(<=|>=|<>|=|<|>)', query[i:], re.IGNORECASE)
            if field_match:
                field_codes = field_match.group(1)  # Can be "ti" or "ti,cl,nov"
                operator = field_match.group(2)
                value_start = i + field_match.end()
                
                # Skip whitespace after operator
                while value_start < len(query) and query[value_start].isspace():
                    value_start += 1
                
                # Extract the complete field value
                value = QueryTokenizer._extract_field_value(query, value_start, operator)
                
                # Store field expression with all field codes
                tokens.append(('field', f"{field_codes}{operator}{value}"))
                i = value_start + len(value)
                continue
            
            # Check for parentheses
            if query[i] in '()':
                tokens.append(('paren', query[i]))
                i += 1
                continue
            
            # Try to match a bare field code (without operator) - treat as fieldcode=*
            bare_field_match = re.match(r'(\w+(?:\s*,\s*\w+)*)', query[i:], re.IGNORECASE)
            if bare_field_match:
                bare_fields = bare_field_match.group(1)
                
                # Check if next non-whitespace character/word is an operator or end marker
                check_pos = i + bare_field_match.end()
                while check_pos < len(query) and query[check_pos].isspace():
                    check_pos += 1
                
                # If we hit end of query, semicolon, or comma, this is a bare field code
                if check_pos >= len(query) or query[check_pos] in '();,':
                    # Treat bare field code as "fieldcode=*" (match any)
                    tokens.append(('field', f"{bare_fields}=*"))
                    i = check_pos
                    continue
                
                # Check if next word is an operator
                next_word_match = re.match(r'(\w+)', query[check_pos:])
                if next_word_match:
                    next_word = next_word_match.group(1).upper()
                    # If next word is a known operator, treat as bare field
                    if next_word in QueryTokenizer.OPERATORS:
                        tokens.append(('field', f"{bare_fields}=*"))
                        i = check_pos
                        continue
            
            # Try to match operator
            word_match = re.match(r'NOT_(?:ADJ|NEAR|SAME|WITH)(?:\d+)?|\w+(?:\d+)?', query[i:], re.IGNORECASE)
            if word_match:
                word = word_match.group(0)
                word_upper = word.upper()
                
                # Check if it's a known operator
                param_match = re.match(r'([A-Z_]+)(\d+)?', word_upper)
                if param_match:
                    base_op = param_match.group(1)
                    if base_op in QueryTokenizer.OPERATORS:
                        tokens.append(('operator', word_upper))
                        i += len(word)
                        continue
            
            # Unknown token - error
            raise ValueError(f"Cannot parse at position {i}: '{query[i]}'")
        
        return tokens
    
    @staticmethod
    def parse_field_expression(expr: str) -> Tuple[List[str], str, str]:
        """
        Parse a field expression into (field_codes, operator, value).
        
        Examples:
            "ti=solar" -> (["ti"], "=", "solar")
            "ti,cl=solar" -> (["ti", "cl"], "=", "solar")
            "pn>=US*" -> (["pn"], ">=", "US*")
            'SSTO=(Corona Virus)' -> (["ssto"], "=", "(Corona Virus)")
        """
        # Use the FIELD_PATTERN to extract field code(s) and operator
        match = QueryTokenizer.FIELD_PATTERN.match(expr)
        if not match:
            raise ValueError(f"Invalid field expression: {expr}")
        
        field_codes_str = match.group(1)  # Can be "ti" or "ti,cl,nov"
        operator = match.group(2)
        
        # Parse comma-separated field codes
        field_codes = [code.strip().lower() for code in field_codes_str.split(',')]
        
        # The value starts right after the operator
        value_start = match.end()
        value = expr[value_start:].lstrip()
        
        if not value:
            raise ValueError(f"Field expression has no value: {expr}")
        
        return field_codes, operator, value
    
    @staticmethod
    def get_operator_info(operator_str: str) -> Dict[str, Any]:
        """
        Get information about an operator including type and parameters.
        
        Args:
            operator_str: Operator string (e.g., "AND", "ADJ3", "NEAR5")
        
        Returns:
            Dictionary with operator information
        """
        upper_op = operator_str.upper()
        param_match = re.match(r'([A-Z_]+)(\d+)?', upper_op)
        
        if not param_match:
            return {'valid': False, 'error': f'Invalid operator format: {operator_str}'}
        
        base_op = param_match.group(1)
        param = param_match.group(2)
        
        if base_op not in QueryTokenizer.OPERATORS:
            return {'valid': False, 'error': f'Unknown operator: {base_op}'}
        
        info = {
            'valid': True,
            'operator': base_op,
            'parameter': int(param) if param else None,
            'type': None,
            'description': None,
            'allow_parameter': False,
            'within_field_only': False,
        }
        
        # Classify operator
        if base_op in QueryTokenizer.BASIC_OPERATORS:
            info['type'] = 'basic_boolean'
            if base_op == 'AND':
                info['description'] = 'Both operands must match'
            elif base_op == 'OR':
                info['description'] = 'At least one operand must match'
            elif base_op == 'NOT':
                info['description'] = 'Operand must not match'
        
        elif base_op in QueryTokenizer.PROXIMITY_OPERATORS:
            info['type'] = 'proximity'
            info['within_field_only'] = True
            if base_op == 'ADJ':
                info['description'] = 'Adjacent (terms within specified distance)'
                info['allow_parameter'] = True
            elif base_op == 'NEAR':
                info['description'] = 'Near (terms within specified distance, any order)'
                info['allow_parameter'] = True
            elif base_op == 'SAME':
                info['description'] = 'Same sentence'
            elif base_op == 'WITH':
                info['description'] = 'Same paragraph/field'
        
        elif base_op in QueryTokenizer.NEGATED_PROXIMITY_OPERATORS:
            info['type'] = 'negated_proximity'
            info['within_field_only'] = True
            if base_op == 'NOT_ADJ':
                info['description'] = 'Not adjacent (patent content only)'
                info['allow_parameter'] = True
            elif base_op == 'NOT_NEAR':
                info['description'] = 'Not near (patent content only)'
                info['allow_parameter'] = True
            elif base_op == 'NOT_SAME':
                info['description'] = 'Not same sentence (patent content only)'
            elif base_op == 'NOT_WITH':
                info['description'] = 'Not same paragraph (patent content only)'
        
        # Validate parameter usage
        if param is not None and not info['allow_parameter']:
            info['valid'] = False
            info['error'] = f"Operator {base_op} does not accept numeric parameters"
        elif param is not None and info['allow_parameter']:
            param_int = int(param)
            if param_int > 99:
                info['valid'] = False
                info['error'] = f"Proximity parameter must be 0-99, got: {param_int}"
        
        return info


class QueryTranslator:
    """Translates Derwent FLD queries to T3 FLD queries."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize translator with field mappings.
        
        Args:
            config_file: Path to XML config file. If None, uses default 'fld_field_mappings.xml'
                        in the same directory as this script.
        """
        if config_file is None:
            # Default to fld_field_mappings.xml in script directory
            script_dir = Path(__file__).parent
            config_file = script_dir / 'fld_field_mappings.xml'
        
        self.config_file = str(config_file)
        self.loader = XMLFieldConfigLoader(self.config_file)
        self.field_mappings = self.loader.load_fld_fields()
        self.tokenizer = QueryTokenizer()
    
    def translate(self, derwent_query: str) -> str:
        """
        Translate a Derwent FLD query to T3 FLD query.
        
        Args:
            derwent_query: Query using Derwent field codes
                          Example: "ti=solar AND pn=US* AND cc=JP"
        
        Returns:
            T3-compatible query
            Example: "ti=solar AND pn=US* AND cc=JP"
        
        Raises:
            ValueError: If query contains invalid syntax
        """
        if not derwent_query or not derwent_query.strip():
            return ""
        
        # Strip outer quotes if query is quoted (handle double-quoted queries)
        query = derwent_query.strip()
        if (query.startswith('"') and query.endswith('"')) or (query.startswith("'") and query.endswith("'")):
            query = query[1:-1].strip()
        
        try:
            tokens = self.tokenizer.tokenize(query)
            translated_tokens = self._translate_tokens(tokens)
            result = self._assemble_query(translated_tokens)
            return result
        except (ValueError, KeyError) as e:
            raise ValueError(f"Query translation failed: {str(e)}")
    
    
    def _translate_tokens(self, tokens: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        Translate field tokens while preserving operators and structure.
        
        Args:
            tokens: Tokenized query
        
        Returns:
            Tokens with field expressions translated
        """
        translated = []
        
        for token_type, token_value in tokens:
            if token_type == 'field':
                new_token = self._translate_field_expression(token_value)
                translated.append(('field', new_token))
            else:
                # Keep operators and parentheses unchanged
                translated.append((token_type, token_value))
        
        return translated
    
    def _translate_field_expression(self, expr: str) -> str:
        """
        Translate a (possibly multi-field) field expression.
        
        Examples:
            Input: "ti=solar"
            Output: "ti=solar" (single field)
            
            Input: "ti,cl=solar"
            Output: "(ti=solar) OR (cl=solar)" (expanded multi-field)
            
            Input: "pa=Intel"
            Output: "pa=Intel" (unmapped field passed through)
            
        Note: Unmapped field codes are passed through unchanged.
        """
        field_codes, operator, value = self.tokenizer.parse_field_expression(expr)
        
        # Translate each field code and collect results
        translated_parts = []
        
        for field_code in field_codes:
            # If field not in mappings, pass through unchanged (unmapped field)
            if field_code not in self.field_mappings:
                translated_parts.append(f"{field_code}{operator}{value}")
                continue
            
            mapping = self.field_mappings[field_code]
            
            # Get the T3 search code
            t3_code = mapping.search_code
            
            # If searchCode is empty/not found, do NOT translate - pass through unchanged
            if not t3_code:
                translated_parts.append(f"{field_code}{operator}{value}")
                continue
            
            # Handle comma-separated search codes from mapping (compound queries)
            if ',' in t3_code:
                # Compound field - create OR expression with all codes
                codes = t3_code.split(',')
                parts = [f"{code.strip()}{operator}{value}" for code in codes]
                translated_parts.append(f"({' OR '.join(parts)})")
            else:
                # Simple field translation
                translated_parts.append(f"{t3_code}{operator}{value}")
        
        # If multiple input field codes, wrap in OR expression
        if len(field_codes) > 1:
            return f"({' OR '.join(translated_parts)})"
        
        # Single field code
        return translated_parts[0]
    
    def _assemble_query(self, tokens: List[Tuple[str, str]]) -> str:
        """Assemble translated tokens back into query string."""
        result = []
        for token_type, token_value in tokens:
            if token_type == 'field':
                result.append(token_value)
            elif token_type == 'operator':
                result.append(f" {token_value} ")
            elif token_type == 'paren':
                result.append(token_value)
        
        return ''.join(result).strip()
    
    def get_field_metadata(self, derwent_code: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about a field mapping.
        
        Args:
            derwent_code: Derwent field code (e.g., 'ti', 'pn')
        
        Returns:
            Dictionary with field information or None if not found
        """
        if derwent_code not in self.field_mappings:
            return None
        
        mapping = self.field_mappings[derwent_code]
        return mapping.to_dict()
    
    def get_all_fields(self) -> Dict[str, Dict[str, str]]:
        """
        Get all available field mappings.
        
        Returns:
            Dictionary mapping field codes to their metadata
        """
        return {code: mapping.to_dict() for code, mapping in self.field_mappings.items()}
    
    def get_sortable_fields(self) -> List[str]:
        """Get list of field codes that support sorting."""
        return [code for code, mapping in self.field_mappings.items() if mapping.sort_code]
    
    def validate_query(self, derwent_query: str) -> Tuple[bool, str]:
        """
        Validate a query without translating it.
        
        Args:
            derwent_query: Query to validate
        
        Returns:
            (is_valid, error_message) - error_message is empty if valid
        """
        try:
            tokens = self.tokenizer.tokenize(derwent_query)
            for token_type, token_value in tokens:
                if token_type == 'field':
                    field_codes, _, _ = self.tokenizer.parse_field_expression(token_value)
                    # Check each field code (now a list) against mappings
                    for field_code in field_codes:
                        if field_code not in self.field_mappings:
                            return False, f"Unknown field code: '{field_code}'"
            return True, ""
        except Exception as e:
            return False, str(e)
    
    def get_translation_info(self) -> Dict[str, Any]:
        """Get information about the translation service."""
        config_info = self.loader.get_config_info()
        return {
            'service': 'Derwent-T3 FLD Query Translator',
            'version': '1.1',
            'config_file': self.config_file,
            'fields_loaded': len(self.field_mappings),
            'config': config_info,
            'supported_operators': {
                'basic_boolean': sorted(list(QueryTokenizer.BASIC_OPERATORS)),
                'proximity': sorted(list(QueryTokenizer.PROXIMITY_OPERATORS)),
                'negated_proximity': sorted(list(QueryTokenizer.NEGATED_PROXIMITY_OPERATORS)),
            },
        }
    
    def get_operator_info(self, operator: str) -> Dict[str, Any]:
        """
        Get detailed information about an operator.
        
        Args:
            operator: Operator name or code (e.g., "AND", "ADJ3", "NEAR5")
        
        Returns:
            Dictionary with operator information and validation
        """
        return QueryTokenizer.get_operator_info(operator)
    
    def list_all_operators(self) -> Dict[str, List[str]]:
        """
        List all supported operators grouped by type.
        
        Returns:
            Dictionary with operator categories
        """
        return {
            'basic_boolean': sorted(list(QueryTokenizer.BASIC_OPERATORS)),
            'proximity': sorted(list(QueryTokenizer.PROXIMITY_OPERATORS)),
            'negated_proximity': sorted(list(QueryTokenizer.NEGATED_PROXIMITY_OPERATORS)),
        }


class TranslationResult:
    """Encapsulates translation result with metadata."""
    
    def __init__(self, original_query: str, translated_query: str, 
                 field_mappings_used: List[str], success: bool, error: Optional[str] = None):
        self.original_query = original_query
        self.translated_query = translated_query
        self.field_mappings_used = field_mappings_used
        self.success = success
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'original_query': self.original_query,
            'translated_query': self.translated_query,
            'field_mappings_used': self.field_mappings_used,
            'error': self.error,
        }
    
    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"{status} Translation: '{self.original_query}' -> '{self.translated_query}'"


def translate_query(derwent_query: str, config_file: Optional[str] = None) -> str:
    """
    Convenience function to translate a single query.
    
    Args:
        derwent_query: Derwent FLD query
        config_file: Optional path to XML config
    
    Returns:
        Translated T3 query
    """
    translator = QueryTranslator(config_file)
    return translator.translate(derwent_query)
