import { defineAgent } from "eve";

export default defineAgent({
  // No sandbox or file tools: this agent reads the web through Nimble and
  // stores data through its own tools.
  defaultTools: false,
  model: "anthropic/claude-sonnet-5.5",
});
