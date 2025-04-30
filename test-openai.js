import OpenAI from 'openai';

// Initialize OpenAI client with API key from environment variables  
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

async function testOpenAI() {
  try {
    console.log("Testing OpenAI connection...");
    
    // Prepare messages for a simple question
    const messages = [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Say hello and confirm you're connected to OpenAI." }
    ];
    
    // Send request to OpenAI
    console.log("Sending request to OpenAI API...");
    const completion = await openai.chat.completions.create({
      model: "gpt-4o",
      messages: messages,
      temperature: 0.7,
      max_tokens: 100,
    });
    
    // Extract and return the response text
    const responseText = completion.choices[0].message.content || "";
    console.log("API Response:", responseText);
    console.log("OpenAI connection test successful!");
    
    return responseText;
  } catch (error) {
    console.error("Error testing OpenAI connection:", error.message);
    if (error.response) {
      console.error("Error status:", error.response.status);
      console.error("Error data:", error.response.data);
    }
    throw new Error(`Failed to connect to OpenAI: ${error.message}`);
  }
}

// Run the test
testOpenAI();