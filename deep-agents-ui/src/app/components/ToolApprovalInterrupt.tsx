"use client";

import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AlertCircle, Check, X, Pencil } from "lucide-react";
import type { ActionRequest, ReviewConfig } from "@/app/types/types";
import { cn } from "@/lib/utils";

// Helper function to parse potentially malformed args (string or numeric-keyed object)
function parseArgs(args: unknown): Record<string, unknown> {
  if (!args) return {};
  
  // If args is a string, try to parse it as JSON
  if (typeof args === 'string') {
    try {
      return JSON.parse(args);
    } catch {
      return { value: args };
    }
  }
  
  // If args is an object with only numeric keys, reconstruct the string
  if (typeof args === 'object' && args !== null) {
    const objArgs = args as Record<string, unknown>;
    const keys = Object.keys(objArgs);
    if (keys.length > 0 && keys.every(k => /^\d+$/.test(k))) {
      try {
        const reconstructedString = keys
          .sort((a, b) => parseInt(a) - parseInt(b))
          .map(k => objArgs[k])
          .join('');
        return JSON.parse(reconstructedString);
      } catch {
        return { raw: keys.map(k => objArgs[k]).join('') };
      }
    }
    return objArgs;
  }
  
  return { value: args };
}

interface ToolApprovalInterruptProps {
  actionRequest: ActionRequest;
  reviewConfig?: ReviewConfig;
  onResume: (value: any) => void;
  isLoading?: boolean;
}

export function ToolApprovalInterrupt({
  actionRequest,
  reviewConfig,
  onResume,
  isLoading,
}: ToolApprovalInterruptProps) {
  const [rejectionMessage, setRejectionMessage] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [editedArgs, setEditedArgs] = useState<Record<string, unknown>>({});
  const [showRejectionInput, setShowRejectionInput] = useState(false);

  // Parse args defensively to handle malformed data
  const parsedArgs = useMemo(() => parseArgs(actionRequest.args), [actionRequest.args]);

  const allowedDecisions = reviewConfig?.allowedDecisions ?? [
    "approve",
    "reject",
    "edit",
  ];

  const handleApprove = () => {
    onResume({
      decisions: [{ type: "approve" }],
    });
  };

  const handleReject = () => {
    if (showRejectionInput) {
      onResume({
        decisions: [
          {
            type: "reject",
            message: rejectionMessage.trim(),
          },
        ],
      });
    } else {
      setShowRejectionInput(true);
    }
  };

  const handleRejectConfirm = () => {
    onResume({
      decisions: [
        {
          type: "reject",
          message: rejectionMessage.trim(),
        },
      ],
    });
  };

  const handleEdit = () => {
    if (isEditing) {
      onResume({
        decisions: [
          {
            type: "edit",
            edited_action: {
              name: actionRequest.name,
              args: editedArgs,
            },
          },
        ],
      });
      setIsEditing(false);
      setEditedArgs({});
    }
  };

  const startEditing = () => {
    setIsEditing(true);
    setEditedArgs(JSON.parse(JSON.stringify(parsedArgs)));
    setShowRejectionInput(false);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditedArgs({});
  };

  const updateEditedArg = (key: string, value: string) => {
    try {
      const parsedValue =
        value.trim().startsWith("{") || value.trim().startsWith("[")
          ? JSON.parse(value)
          : value;
      setEditedArgs((prev) => ({ ...prev, [key]: parsedValue }));
    } catch {
      setEditedArgs((prev) => ({ ...prev, [key]: value }));
    }
  };

  return (
    <div className="w-full rounded-md border border-border bg-muted/30 p-4">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2 text-foreground">
        <AlertCircle
          size={16}
          className="text-yellow-600 dark:text-yellow-400"
        />
        <span className="text-xs font-semibold uppercase tracking-wider">
          Approval Required
        </span>
      </div>

      {/* Description */}
      {actionRequest.description && (
        <p className="mb-3 text-sm text-muted-foreground">
          {actionRequest.description}
        </p>
      )}

      {/* Tool Info Card */}
      <div className="mb-4 rounded-sm border border-border bg-background p-3">
        <div className="mb-2">
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Tool
          </span>
          <p className="mt-1 font-mono text-sm font-medium text-foreground">
            {actionRequest.name}
          </p>
        </div>

        {isEditing ? (
          <div>
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Edit Arguments
            </span>
            <div className="mt-2 space-y-3">
              {Object.entries(parsedArgs).map(([key, value]) => (
                <div key={key}>
                  <label className="mb-1 block text-xs font-medium text-foreground">
                    {key}
                  </label>
                  <Textarea
                    value={
                      editedArgs[key] !== undefined
                        ? typeof editedArgs[key] === "string"
                          ? (editedArgs[key] as string)
                          : JSON.stringify(editedArgs[key], null, 2)
                        : typeof value === "string"
                        ? value
                        : JSON.stringify(value, null, 2)
                    }
                    onChange={(e) => updateEditedArg(key, e.target.value)}
                    className="font-mono text-xs"
                    rows={
                      typeof value === "string" && (value as string).length < 100 ? 2 : 4
                    }
                    disabled={isLoading}
                  />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div>
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Arguments
            </span>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-sm border border-border bg-muted/40 p-2 font-mono text-xs text-foreground">
              {JSON.stringify(parsedArgs, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Rejection Message Input */}
      {showRejectionInput && !isEditing && (
        <div className="mb-4">
          <label className="mb-2 block text-xs font-medium text-foreground">
            Rejection Message (optional)
          </label>
          <Textarea
            value={rejectionMessage}
            onChange={(e) => setRejectionMessage(e.target.value)}
            placeholder="Explain why you're rejecting this action..."
            className="text-sm"
            rows={2}
            disabled={isLoading}
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        {isEditing ? (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={cancelEditing}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleEdit}
              disabled={isLoading}
              className="bg-green-600 text-white hover:bg-green-700 dark:bg-green-600 dark:hover:bg-green-700"
            >
              <Check size={14} />
              {isLoading ? "Saving..." : "Save & Approve"}
            </Button>
          </>
        ) : showRejectionInput ? (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowRejectionInput(false);
                setRejectionMessage("");
              }}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleRejectConfirm}
              disabled={isLoading}
            >
              {isLoading ? "Rejecting..." : "Confirm Reject"}
            </Button>
          </>
        ) : (
          <>
            {allowedDecisions.includes("reject") && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleReject}
                disabled={isLoading}
                className="text-destructive hover:bg-destructive/10"
              >
                <X size={14} />
                Reject
              </Button>
            )}
            {allowedDecisions.includes("edit") && (
              <Button
                variant="outline"
                size="sm"
                onClick={startEditing}
                disabled={isLoading}
              >
                <Pencil size={14} />
                Edit
              </Button>
            )}
            {allowedDecisions.includes("approve") && (
              <Button
                size="sm"
                onClick={handleApprove}
                disabled={isLoading}
                className={cn(
                  "bg-green-600 text-white hover:bg-green-700",
                  "dark:bg-green-600 dark:hover:bg-green-700"
                )}
              >
                <Check size={14} />
                {isLoading ? "Approving..." : "Approve"}
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
