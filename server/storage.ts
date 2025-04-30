import { agents, chatMessages, users, type User, type InsertUser, type Agent, type InsertAgent, type ChatMessage, type InsertChatMessage } from "@shared/schema";

// Interface for storage operations
export interface IStorage {
  // User operations (keeping existing)
  getUser(id: number): Promise<User | undefined>;
  getUserByUsername(username: string): Promise<User | undefined>;
  createUser(user: InsertUser): Promise<User>;
  
  // Agent operations
  getAgents(): Promise<Agent[]>;
  getAgent(id: number): Promise<Agent | undefined>;
  createAgent(agent: InsertAgent): Promise<Agent>;
  updateAgent(id: number, agent: Partial<InsertAgent>): Promise<Agent | undefined>;
  deleteAgent(id: number): Promise<boolean>;
  
  // Chat operations
  getChatMessages(agentId: number): Promise<ChatMessage[]>;
  createChatMessage(message: InsertChatMessage): Promise<ChatMessage>;
}

export class MemStorage implements IStorage {
  private users: Map<number, User>;
  private agentsMap: Map<number, Agent>;
  private chatMessagesMap: Map<number, ChatMessage>;
  private userIdCounter: number;
  private agentIdCounter: number;
  private messageIdCounter: number;

  constructor() {
    this.users = new Map();
    this.agentsMap = new Map();
    this.chatMessagesMap = new Map();
    this.userIdCounter = 1;
    this.agentIdCounter = 1;
    this.messageIdCounter = 1;
    
    // Add some initial agents for demo
    this.createAgent({
      name: "Research Assistant",
      systemPrompt: "You are a helpful assistant for academic research and information gathering.",
      model: "gpt-4o"
    });
    
    this.createAgent({
      name: "Code Helper",
      systemPrompt: "You help with programming problems, code review, and debugging.",
      model: "gpt-4o"
    });
    
    this.createAgent({
      name: "Creative Writer",
      systemPrompt: "You are specialized in creative writing, story development, and content creation.",
      model: "gpt-4o"
    });
    
    // Add initial messages for Research Assistant
    this.createChatMessage({
      agentId: 1,
      role: "assistant",
      content: "Hello! I'm your Research Assistant. I can help you find information, summarize content, and answer questions about various topics. How can I assist you today?"
    });
    
    this.createChatMessage({
      agentId: 1,
      role: "user",
      content: "I need information about the latest advancements in quantum computing. Can you give me a brief overview?"
    });
    
    this.createChatMessage({
      agentId: 1,
      role: "assistant",
      content: "Recent advancements in quantum computing include:\n\n- Development of processors with over 100 qubits by companies like IBM and Google\n- Progress in error correction techniques to improve quantum reliability\n- Quantum advantage demonstrations in specific computational tasks\n- Advances in quantum algorithms for optimization and machine learning\n- New quantum programming frameworks making development more accessible\n\nWould you like me to elaborate on any of these areas or provide more specific information about a particular aspect of quantum computing?"
    });
  }

  // User methods (existing)
  async getUser(id: number): Promise<User | undefined> {
    return this.users.get(id);
  }

  async getUserByUsername(username: string): Promise<User | undefined> {
    return Array.from(this.users.values()).find(
      (user) => user.username === username,
    );
  }

  async createUser(insertUser: InsertUser): Promise<User> {
    const id = this.userIdCounter++;
    const user: User = { ...insertUser, id };
    this.users.set(id, user);
    return user;
  }
  
  // Agent methods
  async getAgents(): Promise<Agent[]> {
    return Array.from(this.agentsMap.values()).sort((a, b) => 
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
  }
  
  async getAgent(id: number): Promise<Agent | undefined> {
    return this.agentsMap.get(id);
  }
  
  async createAgent(insertAgent: InsertAgent): Promise<Agent> {
    const id = this.agentIdCounter++;
    const now = new Date();
    const agent: Agent = { 
      ...insertAgent, 
      id,
      createdAt: now,
      updatedAt: now
    };
    this.agentsMap.set(id, agent);
    return agent;
  }
  
  async updateAgent(id: number, updates: Partial<InsertAgent>): Promise<Agent | undefined> {
    const existingAgent = this.agentsMap.get(id);
    if (!existingAgent) return undefined;
    
    const updatedAgent: Agent = {
      ...existingAgent,
      ...updates,
      updatedAt: new Date()
    };
    
    this.agentsMap.set(id, updatedAgent);
    return updatedAgent;
  }
  
  async deleteAgent(id: number): Promise<boolean> {
    return this.agentsMap.delete(id);
  }
  
  // Chat methods
  async getChatMessages(agentId: number): Promise<ChatMessage[]> {
    return Array.from(this.chatMessagesMap.values())
      .filter(message => message.agentId === agentId)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }
  
  async createChatMessage(insertMessage: InsertChatMessage): Promise<ChatMessage> {
    const id = this.messageIdCounter++;
    const message: ChatMessage = {
      ...insertMessage,
      id,
      timestamp: new Date()
    };
    
    this.chatMessagesMap.set(id, message);
    
    // Update the agent's updatedAt timestamp
    const agent = this.agentsMap.get(insertMessage.agentId);
    if (agent) {
      this.agentsMap.set(agent.id, {
        ...agent, 
        updatedAt: new Date()
      });
    }
    
    return message;
  }
}

export const storage = new MemStorage();
