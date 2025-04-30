import { useEffect, useState } from "react";
import { Moon, Sun, Settings, User, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Header() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || 
      (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      setTheme('dark');
    } else {
      setTheme('light');
    }
  }, []);
  
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
    
    setTheme(newTheme);
  };

  return (
    <header className="bg-primary text-white shadow-md z-10">
      <div className="container mx-auto px-4 py-3 flex justify-between items-center">
        <div className="flex items-center space-x-2">
          <Bot className="text-2xl" />
          <h1 className="text-xl font-medium">AgentGPT</h1>
        </div>
        <div className="flex items-center space-x-4">
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={toggleTheme}
            className="rounded-full hover:bg-primary-dark text-white"
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </Button>
          
          <Button 
            variant="ghost" 
            size="icon"
            className="rounded-full hover:bg-primary-dark text-white"
          >
            <Settings size={20} />
          </Button>
          
          <div className="relative">
            <Button 
              variant="ghost"
              className="flex items-center space-x-1 rounded-full hover:bg-primary-dark text-white"
            >
              <User size={20} />
              <span className="hidden md:inline text-sm font-medium">User</span>
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
