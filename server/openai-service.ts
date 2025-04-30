import OpenAI from "openai";
import { log } from "./vite";

// Initialize OpenAI client with API key from environment variables
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Check if we have a valid API key
if (!process.env.OPENAI_API_KEY) {
  log("WARNING: Missing OPENAI_API_KEY environment variable", "openai-service");
}

export interface ChatCompletionOptions {
  systemPrompt: string;
  messages: { role: 'user' | 'assistant'; content: string }[];
  model: string;
}

/**
 * Generates a chat completion response using OpenAI's API
 */
export async function generateChatCompletion(options: ChatCompletionOptions): Promise<string> {
  try {
    const { systemPrompt, messages, model } = options;

    // Prepate the messages array with the system prompt and chat history
    const apiMessages = [
      { role: "system", content: systemPrompt } as const,
      ...messages.map(msg => ({
        role: msg.role,
        content: msg.content,
      })),
    ];

    log(`Sending request to OpenAI with model: ${model}`, "openai-service");
    
    // Send request to OpenAI
    const completion = await openai.chat.completions.create({
      model: model, // the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
      messages: apiMessages,
      temperature: 0.7,
      max_tokens: 1000,
    });

    // Extract and return the response text
    const responseText = completion.choices[0].message.content || "";
    log(`Received response from OpenAI (${responseText.length} chars)`, "openai-service");
    
    return responseText;
  } catch (error: any) {
    log(`Error generating chat completion: ${error.message}`, "openai-service");
    throw new Error(`Failed to generate AI response: ${error.message}`);
  }
}