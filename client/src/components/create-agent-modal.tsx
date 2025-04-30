import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { CreateAgentRequest, defaultAgent, availableModels, retrieverStrategies } from "@/lib/types";
import { useToast } from "@/hooks/use-toast";
import { X } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

interface CreateAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CreateAgentModal({ 
  isOpen, 
  onClose 
}: CreateAgentModalProps) {
  const [formData, setFormData] = useState<CreateAgentRequest>(defaultAgent);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { toast } = useToast();

  const createAgentMutation = useMutation({
    mutationFn: async (data: CreateAgentRequest) => {
      return await apiRequest('/api/agents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/agents'] });
      toast({
        title: "Agent created",
        description: "Your new agent has been successfully created.",
      });
      handleClose();
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: `Failed to create agent: ${error.message}`,
        variant: "destructive",
      });
    }
  });

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.name.trim()) {
      newErrors.name = "Agent name is required";
    }
    
    if (!formData.systemPrompt.trim()) {
      newErrors.systemPrompt = "System prompt is required";
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    createAgentMutation.mutate(formData);
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const handleModelChange = (value: string) => {
    setFormData((prev) => ({ ...prev, model: value }));
  };
  
  const handleRetrieverStrategyChange = (value: string) => {
    setFormData((prev) => ({ ...prev, retrieverStrategy: value }));
  };

  const handleClose = () => {
    setFormData(defaultAgent);
    setErrors({});
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create New Agent</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label htmlFor="name">Agent Name</Label>
            <Input
              id="name"
              name="name"
              placeholder="e.g., Research Assistant"
              value={formData.name}
              onChange={handleChange}
              className={errors.name ? "border-status-error" : ""}
              required
            />
            {errors.name && (
              <p className="text-xs text-status-error">{errors.name}</p>
            )}
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="model">Model</Label>
            <Select 
              value={formData.model} 
              onValueChange={handleModelChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a model" />
              </SelectTrigger>
              <SelectContent>
                {availableModels.map((model) => (
                  <SelectItem key={model.value} value={model.value}>
                    {model.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="systemPrompt">System Prompt</Label>
            <Textarea
              id="systemPrompt"
              name="systemPrompt"
              placeholder="Enter instructions for your agent..."
              value={formData.systemPrompt}
              onChange={handleChange}
              className={`min-h-[120px] ${errors.systemPrompt ? "border-status-error" : ""}`}
              required
            />
            {errors.systemPrompt ? (
              <p className="text-xs text-status-error">{errors.systemPrompt}</p>
            ) : (
              <p className="text-xs text-neutral">Describe your agent's role, personality, and guidelines for interaction.</p>
            )}
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="retrieverStrategy">Document Retrieval Strategy</Label>
            <Select
              value={formData.retrieverStrategy}
              onValueChange={handleRetrieverStrategyChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a retrieval strategy" />
              </SelectTrigger>
              <SelectContent>
                {retrieverStrategies.map((strategy) => (
                  <SelectItem key={strategy.value} value={strategy.value}>
                    {strategy.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-neutral">
              {retrieverStrategies.find(s => s.value === formData.retrieverStrategy)?.description || 
              "Choose how the agent retrieves information from documents."}
            </p>
          </div>
          
          <DialogFooter className="mt-6">
            <Button variant="outline" type="button" onClick={handleClose}>
              Cancel
            </Button>
            <Button 
              type="submit" 
              disabled={createAgentMutation.isPending}
              className="min-w-[120px]"
            >
              {createAgentMutation.isPending ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  Initializing...
                </>
              ) : "Create Agent"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
