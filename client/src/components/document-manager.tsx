import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Agent } from "@/lib/types";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FileIcon, UploadIcon, Trash2Icon, BookOpenIcon, FileTextIcon, FileSpreadsheetIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

interface Document {
  id: string;
  filename: string;
  type: string;
  description: string;
  agentId: number;
  uploadedAt: string;
}

interface DocumentManagerProps {
  agent: Agent;
}

export default function DocumentManager({ agent }: DocumentManagerProps) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [ragQuery, setRagQuery] = useState("");
  
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Query for agent documents
  const {
    data: documents = [],
    isLoading: documentsLoading,
    error: documentsError,
  } = useQuery({
    queryKey: ["/api/agents", agent.id, "documents"],
    queryFn: () => apiRequest(`/api/agents/${agent.id}/documents`),
  });

  // Upload document mutation
  const uploadMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      return apiRequest(
        `/api/agents/${agent.id}/documents`,
        {
          method: "POST",
          body: formData,
          headers: {
            // Don't set Content-Type here as it will be set automatically with boundary
          },
        },
        true, // Skip JSON parsing
      );
    },
    onSuccess: () => {
      // Reset form
      setFile(null);
      setDescription("");
      setUploadDialogOpen(false);

      // Invalidate document cache
      queryClient.invalidateQueries({ queryKey: ["/api/agents", agent.id, "documents"] });

      // Show success toast
      toast({
        title: "Document uploaded",
        description: "Your document has been successfully uploaded.",
      });
    },
    onError: (error: any) => {
      console.error("Upload error:", error);
      toast({
        title: "Upload failed",
        description: error.message || "Failed to upload document. Please try again.",
        variant: "destructive",
      });
    },
  });

  // Delete document mutation
  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => {
      return apiRequest(`/api/documents/${documentId}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      // Invalidate document cache
      queryClient.invalidateQueries({ queryKey: ["/api/agents", agent.id, "documents"] });

      // Show success toast
      toast({
        title: "Document deleted",
        description: "The document has been successfully deleted.",
      });
    },
    onError: (error: any) => {
      console.error("Delete error:", error);
      toast({
        title: "Deletion failed",
        description: error.message || "Failed to delete document. Please try again.",
        variant: "destructive",
      });
    },
  });

  // RAG query mutation
  const ragMutation = useMutation({
    mutationFn: (query: string) => {
      return apiRequest(`/api/agents/${agent.id}/rag`, {
        method: "POST",
        body: JSON.stringify({ query }),
        headers: {
          "Content-Type": "application/json",
        },
      });
    },
    onSuccess: (data) => {
      // Invalidate messages to show the response in chat
      queryClient.invalidateQueries({ queryKey: ["/api/agents", agent.id, "messages"] });

      // Reset RAG query
      setRagQuery("");

      // Show success toast
      toast({
        title: "Query processed",
        description: "Your document query has been processed.",
      });
    },
    onError: (error: any) => {
      console.error("RAG query error:", error);
      toast({
        title: "Query failed",
        description: error.message || "Failed to process your query. Please try again.",
        variant: "destructive",
      });
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!file) {
      toast({
        title: "No file selected",
        description: "Please select a file to upload.",
        variant: "destructive",
      });
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

  const handleDelete = (documentId: string) => {
    if (confirm("Are you sure you want to delete this document?")) {
      deleteMutation.mutate(documentId);
    }
  };

  const handleRagQuery = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!ragQuery.trim()) {
      return;
    }

    ragMutation.mutate(ragQuery);
  };

  // Function to get icon based on document type
  const getDocumentIcon = (type: string) => {
    switch (type) {
      case "pdf":
        return <FileIcon className="h-5 w-5" />;
      case "docx":
        return <FileTextIcon className="h-5 w-5" />;
      case "csv":
        return <FileSpreadsheetIcon className="h-5 w-5" />;
      case "excel":
        return <FileSpreadsheetIcon className="h-5 w-5" />;
      default:
        return <FileIcon className="h-5 w-5" />;
    }
  };

  // Format date in a more readable format
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + " " + date.toLocaleTimeString();
  };

  return (
    <Card className="w-full mb-6">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-xl font-bold">Document Management</CardTitle>
        <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <UploadIcon className="mr-2 h-4 w-4" />
              Upload Document
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Upload Document</DialogTitle>
              <DialogDescription>
                Upload documents (PDF, Word, CSV) for the agent to use as reference.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleUpload} className="space-y-4">
              <div className="grid w-full max-w-sm items-center gap-1.5">
                <Input
                  id="document"
                  type="file"
                  accept=".pdf,.docx,.doc,.csv,.xlsx,.xls"
                  onChange={handleFileChange}
                />
                <p className="text-sm text-gray-500">
                  Supported formats: PDF, Word, CSV, Excel (.xlsx/.xls)
                </p>
                <p className="text-xs text-amber-600 mt-1">
                  Note: Large files may take several minutes to process due to AI indexing.
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
                      {file && file.type.includes('excel') || file?.name.endsWith('.xlsx') || file?.name.endsWith('.xls') 
                        ? "Processing Excel file..." 
                        : file?.type.includes('csv') 
                          ? "Processing CSV data..." 
                          : "Uploading..."}
                    </>
                  ) : (
                    "Upload"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Document search form */}
          <form onSubmit={handleRagQuery} className="flex w-full items-center gap-2">
            <Input
              placeholder="Ask a question about your documents..."
              value={ragQuery}
              onChange={(e) => setRagQuery(e.target.value)}
              className="flex-1"
            />
            <Button 
              type="submit" 
              disabled={!ragQuery.trim() || ragMutation.isPending}
            >
              {ragMutation.isPending ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <BookOpenIcon className="h-4 w-4" />
              )}
            </Button>
          </form>

          {/* Documents list */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-gray-500">
              {documentsLoading ? (
                "Loading documents..."
              ) : documents.length === 0 ? (
                "No documents uploaded yet"
              ) : (
                `${documents.length} Document${documents.length !== 1 ? "s" : ""}`
              )}
            </h3>
            {documentsLoading ? (
              <div className="flex justify-center py-4">
                <Spinner className="h-6 w-6" />
              </div>
            ) : (
              <ul className="space-y-2">
                {documents.map((doc: Document) => (
                  <li
                    key={doc.id}
                    className="flex items-center justify-between rounded-md border p-2 text-sm"
                  >
                    <div className="flex items-center">
                      <div className="mr-2 text-gray-500">
                        {getDocumentIcon(doc.type)}
                      </div>
                      <div>
                        <p className="font-medium">{doc.filename}</p>
                        <p className="text-xs text-gray-500">
                          {doc.description} • {formatDate(doc.uploadedAt)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{doc.type.toUpperCase()}</Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(doc.id)}
                        disabled={deleteMutation.isPending}
                      >
                        {deleteMutation.isPending ? (
                          <Spinner className="h-4 w-4" />
                        ) : (
                          <Trash2Icon className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}