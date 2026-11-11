"use client";

import { useChat } from "@ai-sdk/react";
import { getToolOrDynamicToolName, isToolOrDynamicToolUIPart } from "ai";
import { useState } from "react";

export default function Page() {
  const { messages, sendMessage, status } = useChat();
  const [input, setInput] = useState("");

  return (
    <main>
      <h1>Support Desk</h1>
      {messages.map((message) => (
        <div key={message.id} style={{ margin: "12px 0" }}>
          <strong>{message.role === "user" ? "You" : "Agent"}:</strong>
          {message.parts.map((part, i) => {
            if (part.type === "text") return <span key={i}> {part.text}</span>;
            if (isToolOrDynamicToolUIPart(part)) {
              return <em key={i}> (checked {getToolOrDynamicToolName(part)})</em>;
            }
            return null;
          })}
        </div>
      ))}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!input.trim()) return;
          sendMessage({ text: input });
          setInput("");
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Where is order A-1001?"
          disabled={status !== "ready"}
          style={{ width: "100%", padding: 8 }}
        />
      </form>
    </main>
  );
}
