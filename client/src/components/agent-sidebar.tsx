import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Agent } from "@/lib/types";
import { getTimeAgo, retrieverStrategies } from "@/lib/types";
import { PlusCircle, Bot, Pencil, Trash2, Clock, Brain, FileIcon, FileTextIcon, FileSpreadsheetIcon, UploadIcon, RefreshCw, Database } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest } from "@/lib/queryClient";

interface Document {
  id: string;
  filename: string;
  type: string;
  description: string;
  agentId: number;
  uploadedAt: string;
}

interface AgentSidebarProps {
  agents: Agent[];
  selectedAgentId: number | null;
  onSelectAgent: (id: number) => void;
  onCreateAgent: () => void;
  onDeleteAgent: (id: number) => void;
  isLoading: boolean;
  onSelectDocument?: (documentId: string | null) => void; 
}

export default function AgentSidebar({
  agents,
  selectedAgentId,
  onSelectAgent,
  onCreateAgent,
  onDeleteAgent,
  isLoading,
  onSelectDocument = () => {}
}: AgentSidebarProps) {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");

  // Fetch documents for the selected agent
  const {
    data: documents = [],
    isLoading: documentsLoading,
    refetch: refetchDocuments
  } = useQuery({
    queryKey: ['/api/agents', selectedAgentId, 'documents'],
    queryFn: () => selectedAgentId ? apiRequest(`/api/agents/${selectedAgentId}/documents`) : Promise.resolve([]),
    enabled: !!selectedAgentId,
  });

  // Upload document mutation
  const uploadMutation = {
    isPending: false,
    mutate: async (formData: FormData) => {
      try {
        await apiRequest(
          `/api/agents/${selectedAgentId}/documents`,
          {
            method: "POST",
            body: formData,
          },
          true, // Skip JSON parsing
        );
        
        // Reset form
        setFile(null);
        setDescription("");
        setUploadDialogOpen(false);
        
        // Refetch documents
        refetchDocuments();
      } catch (error) {
        console.error("Upload error:", error);
        alert("Failed to upload document: " + (error as Error).message);
      }
    }
  };

  // Delete document mutation
  const deleteMutation = {
    isPending: false,
    mutate: async (documentId: string) => {
      try {
        await apiRequest(`/api/documents/${documentId}`, {
          method: "DELETE",
        });
        
        // If the deleted document was selected, reset selection
        if (selectedDocumentId === documentId) {
          setSelectedDocumentId(null);
          onSelectDocument(null);
        }
        
        // Refetch documents
        refetchDocuments();
      } catch (error) {
        console.error("Delete error:", error);
        alert("Failed to delete document: " + (error as Error).message);
      }
    }
  };

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  // Handle document upload
  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!file || !selectedAgentId) {
      alert("Please select a file to upload");
      return;
    }

    // Create form data
    const formData = new FormData();
    formData.append("file", file);
    if (description) {
      formData.append("description", description);
    }

    // Upload the file
    uploadMutation.mutate(formData);
  };

  // Handle document selection
  const handleSelectDocument = (documentId: string) => {
    if (selectedDocumentId === documentId) {
      // Deselect if already selected
      setSelectedDocumentId(null);
      onSelectDocument(null);
    } else {
      // Select the document
      setSelectedDocumentId(documentId);
      onSelectDocument(documentId);
    }
  };

  // Handle document deletion
  const handleDeleteDocument = (documentId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this document?")) {
      deleteMutation.mutate(documentId);
    }
  };

  // Get document icon based on type
  const getDocumentIcon = (type: string) => {
    switch (type) {
      case "pdf":
        return <FileIcon size={14} />;
      case "docx":
        return <FileTextIcon size={14} />;
      case "excel":
        return <FileSpreadsheetIcon size={14} />;
      default:
        return <FileIcon size={14} />;
    }
  };

  // Format date in a more readable format
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString();
  };
  
  const renderAgentSkeletons = () => {
    return Array(3).fill(0).map((_, index) => (
      <div key={`skeleton-${index}`} className="bg-neutral-lightest dark:bg-neutral-dark p-3 rounded-lg mb-3 border-l-4 border-neutral">
        <div className="flex justify-between items-start">
          <Skeleton className="h-5 w-32 mb-2" />
          <div className="flex gap-1">
            <Skeleton className="h-6 w-6 rounded" />
            <Skeleton className="h-6 w-6 rounded" />
          </div>
        </div>
        <Skeleton className="h-4 w-full mb-1" />
        <Skeleton className="h-4 w-3/4 mb-2" />
        <div className="flex justify-between items-center mt-2">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
    ));
  };

  return (
    <aside className="w-full md:w-72 lg:w-80 flex flex-col h-full overflow-auto pb-20 md:pb-0">
      <div className="flex flex-col gap-4">
        <button 
          onClick={onCreateAgent}
          className="w-full bg-primary hover:bg-primary-dark text-white py-3 px-4 rounded-lg shadow transition-colors flex items-center justify-center gap-2"
        >
          <PlusCircle size={18} />
          <span>Create New Agent</span>
        </button>
        
        <div className="bg-white dark:bg-neutral-darkest rounded-lg shadow p-3">
          <h2 className="text-lg font-medium mb-2 flex items-center">
            <Bot className="mr-2" size={18} />
            My Agents
          </h2>
          
          {isLoading ? (
            renderAgentSkeletons()
          ) : agents.length === 0 ? (
            <div className="text-center p-4 text-neutral">
              <p>No agents found. Create your first agent to get started.</p>
            </div>
          ) : (
            agents.map((agent: Agent) => (
              <div 
                key={agent.id} 
                className={`agent-card bg-neutral-lightest dark:bg-neutral-dark p-3 rounded-lg mb-3 border-l-4 
                  ${selectedAgentId === agent.id ? 'border-primary' : 'border-neutral'}
                  cursor-pointer hover:shadow-md transition-shadow`}
                onClick={() => onSelectAgent(agent.id)}
              >
                <div className="flex justify-between items-start">
                  <h3 className="font-medium text-base">{agent.name}</h3>
                  <div className="flex gap-1">
                    <button 
                      className="text-neutral-dark hover:text-neutral-darkest dark:text-neutral dark:hover:text-white p-1 rounded"
                      onClick={(e) => {
                        e.stopPropagation();
                        // Edit functionality would go here
                        alert("Edit functionality not implemented in this demo");
                      }}
                    >
                      <Pencil size={14} />
                    </button>
                    <button 
                      className="text-neutral-dark hover:text-status-error dark:text-neutral dark:hover:text-status-error p-1 rounded"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteAgent(agent.id);
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                <p className="text-sm text-neutral-dark dark:text-neutral-light mt-1 line-clamp-2">
                  {agent.systemPrompt}
                </p>
                <div className="flex flex-wrap gap-y-1 justify-between items-center mt-2 text-xs text-neutral">
                  <span className="flex items-center mr-2">
                    <Brain className="mr-1" size={12} />
                    {agent.model}
                  </span>
                  {agent.retrieverStrategy && (
                    <span className="flex items-center">
                      <Database className="mr-1" size={12} />
                      {retrieverStrategies.find(s => s.value === agent.retrieverStrategy)?.label || agent.retrieverStrategy}
                    </span>
                  )}
                  <span className="flex items-center">
                    <Clock className="mr-1" size={12} />
                    Updated {getTimeAgo(agent.updatedAt)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
        
        {/* Documents section - only show when an agent is selected */}
        {selectedAgentId && (
          <div className="bg-white dark:bg-neutral-darkest rounded-lg shadow p-3">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-lg font-medium flex items-center">
                <FileIcon className="mr-2" size={18} />
                Documents
              </h2>
              
              {/* Upload document dialog */}
              <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline" className="gap-1">
                    <UploadIcon size={14} />
                    <span>Upload</span>
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Upload Document</DialogTitle>
                    <DialogDescription>
                      Upload documents (PDF, Word, Excel) for the agent to use as reference.
                    </DialogDescription>
                  </DialogHeader>
                  <form onSubmit={handleUpload} className="space-y-4">
                    <div className="grid w-full max-w-sm items-center gap-1.5">
                      <Input
                        id="document"
                        type="file"
                        accept=".pdf,.docx,.doc,.xlsx,.xls"
                        onChange={handleFileChange}
                      />
                      <p className="text-sm text-gray-500">
                        Supported formats: PDF, Word, Excel
                      </p>
                    </div>
                    <div className="grid w-full gap-1.5">
                      <Textarea
                        id="description"
                        placeholder="Document description (optional)"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                      />
                    </div>
                    <DialogFooter>
                      <Button 
                        type="button" 
                        variant="outline" 
                        onClick={() => setUploadDialogOpen(false)}
                      >
                        Cancel
                      </Button>
                      <Button 
                        type="submit" 
                        disabled={!file || uploadMutation.isPending}
                      >
                        {uploadMutation.isPending ? (
                          <>
                            <Spinner className="mr-2 h-4 w-4" />
                            Uploading...
                          </>
                        ) : (
                          "Upload"
                        )}
                      </Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
            
            {/* Documents list */}
            {documentsLoading ? (
              <div className="text-center py-4">
                <Spinner className="mx-auto h-6 w-6" />
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center p-3 text-sm text-neutral">
                <p>No documents uploaded yet.</p>
                <p className="mt-1">Upload documents to enhance your agent's knowledge.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((doc: Document) => (
                  <div
                    key={doc.id}
                    className={`flex items-center justify-between p-2 rounded-md text-sm cursor-pointer hover:bg-neutral-lightest dark:hover:bg-neutral-dark ${
                      selectedDocumentId === doc.id ? 'bg-neutral-lightest dark:bg-neutral-dark' : ''
                    }`}
                    onClick={() => handleSelectDocument(doc.id)}
                  >
                    <div className="flex items-center flex-1 min-w-0">
                      <div className="text-neutral-dark dark:text-neutral mr-2">
                        {getDocumentIcon(doc.type)}
                      </div>
                      <div className="truncate">
                        <div className="font-medium truncate">{doc.filename}</div>
                        <div className="text-xs text-neutral truncate">
                          {doc.description || "No description"} • {formatDate(doc.uploadedAt)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-2">
                      <Badge variant="outline" className="text-xs">{doc.type.toUpperCase()}</Badge>
                      <button
                        className="text-neutral-dark hover:text-status-error dark:text-neutral p-1 rounded"
                        onClick={(e) => handleDeleteDocument(doc.id, e)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {/* Refresh documents button */}
            <div className="mt-3 text-center">
              <Button
                variant="ghost"
                size="sm"
                className="text-xs gap-1"
                onClick={() => refetchDocuments()}
              >
                <RefreshCw size={12} />
                <span>Refresh Documents</span>
              </Button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
