// Web Search Agent runs are billable and gated behind approval, which would
// stall an unattended factory run. Agents here use Search and Extract.
import { disableTool } from "eve/tools";

export default disableTool();
