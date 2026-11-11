import { defineDynamic, defineMcpClientConnection } from "eve/connections";
import type { ApprovalContext, ApprovalStatus } from "eve/tools/approval";
import { LINEAR_CONNECTOR, linearAuth } from "../lib/constants.js";
import { isAutonomous } from "../lib/trust.js";

/**
 * Linear MCP connection for creating and cross-referencing issues.
 *
 * @remarks
 * - Points at Linear's hosted MCP server and authenticates with the shared
 *   app-scoped `linearAuth` from `agent/lib/constants.ts`, so this connection
 *   and any tool calling the Linear API directly share one installation and
 *   one set of scopes. Tokens are resolved per call and never exposed to the
 *   model.
 * - The connection-wide approval predicate denies unattended factory runs, so
 *   a prompt-injected labeled issue cannot fan out into the tracker. Every
 *   attended session keeps the tools ungated: Linear writes are app-scoped
 *   and reversible, as before.
 * - Optional: with no `LINEAR_CONNECTOR` set, the dynamic definition returns
 *   `null` and the factory has no Linear tools.
 */
export default defineDynamic(() =>
  LINEAR_CONNECTOR && linearAuth
    ? defineMcpClientConnection({
        approval: (ctx: ApprovalContext): ApprovalStatus =>
          isAutonomous(ctx.session.auth.current)
            ? {
                reason: "Unattended factory runs do not write to Linear.",
                type: "denied",
              }
            : "not-applicable",
        auth: linearAuth,
        description:
          "Linear workspace: issues, projects, cycles, and comments.",
        instanceKey: LINEAR_CONNECTOR,
        url: "https://mcp.linear.app/mcp",
      })
    : null
);
