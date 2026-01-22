// components/dag/DAGFilesView.tsx
'use client';

import { useState, useEffect, useMemo } from 'react';
import { 
  FileText, 
  Code, 
  Image, 
  Database, 
  File, 
  Download,
  Eye,
  Search,
  Filter,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  AlertCircle,
  X
} from 'lucide-react';
import { getApiUrl } from '@/lib/config';

interface DAGFilesViewProps {
  runId: string;
  refreshTrigger?: number;  // Increment this to trigger a refresh
}

interface FileNode {
  id: string;
  file_path: string;
  file_name: string;
  file_type: string;
  size_bytes: number;
  node_id: string;
  agent_name?: string;
  created_at: string;
  file_content?: string;
  content_type?: string;
  encoding?: string;
  mime_type?: string;
}

export function DAGFilesView({ runId, refreshTrigger }: DAGFilesViewProps) {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list');
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());

  // Fetch files on mount, when runId changes, or when refreshTrigger changes
  useEffect(() => {
    fetchFiles();
  }, [runId, refreshTrigger]);

  const fetchFiles = async () => {
    if (!runId) return;
    
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(getApiUrl(`/api/runs/${runId}/files`));
      if (!response.ok) {
        throw new Error(`Failed to fetch files: ${response.statusText}`);
      }
      const data = await response.json();
      setFiles(data.files || []);
    } catch (err) {
      console.error('Error fetching files:', err);
      setError(err instanceof Error ? err.message : 'Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  // Filter files
  const filteredFiles = useMemo(() => {
    return files.filter(file => {
      const matchesSearch = searchQuery === '' || 
        file.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        file.file_path.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesType = fileTypeFilter === 'all' || 
        (fileTypeFilter === 'code' && file.file_name.match(/\.(py|js|ts|tsx|jsx|json|yaml|yml)$/)) ||
        (fileTypeFilter === 'data' && file.file_name.match(/\.(csv|txt|md|json)$/)) ||
        (fileTypeFilter === 'images' && file.file_name.match(/\.(png|jpg|jpeg|gif|svg)$/)) ||
        (fileTypeFilter === 'logs' && file.file_name.match(/\.(log|txt)$/));
      
      return matchesSearch && matchesType;
    });
  }, [files, searchQuery, fileTypeFilter]);

  // Build file tree structure
  const fileTree = useMemo(() => {
    const tree: any = {};
    
    filteredFiles.forEach(file => {
      const parts = file.file_path.split('/');
      let current = tree;
      
      parts.forEach((part, index) => {
        if (index === parts.length - 1) {
          // It's a file
          if (!current._files) current._files = [];
          current._files.push(file);
        } else {
          // It's a directory
          if (!current[part]) current[part] = {};
          current = current[part];
        }
      });
    });
    
    return tree;
  }, [filteredFiles]);

  const getFileIcon = (fileName: string) => {
    if (fileName.endsWith('.py')) return <Code className="w-4 h-4 text-blue-400" />;
    if (fileName.endsWith('.json') || fileName.endsWith('.yaml')) return <Code className="w-4 h-4 text-yellow-400" />;
    if (fileName.match(/\.(png|jpg|jpeg|gif|svg)$/)) return <Image className="w-4 h-4 text-purple-400" />;
    if (fileName.match(/\.(csv|txt|md)$/)) return <FileText className="w-4 h-4 text-green-400" />;
    if (fileName.match(/\.(db|sql)$/)) return <Database className="w-4 h-4 text-orange-400" />;
    return <File className="w-4 h-4 text-gray-400" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleFileClick = async (file: FileNode) => {
    setSelectedFile(file);
    
    // Fetch file content if not already loaded and it's a text file
    if (!file.file_content) {
      setLoadingContent(true);
      try {
        const response = await fetch(getApiUrl(`/api/files/content?file_path=${encodeURIComponent(file.file_path)}`));
        if (response.ok) {
          const data = await response.json();
          if (data.content) {
            // Store content along with metadata
            setSelectedFile({ 
              ...file, 
              file_content: data.content,
              content_type: data.content_type,
              encoding: data.encoding,
              mime_type: data.mime_type
            });
          } else if (data.content_type === 'binary') {
            setSelectedFile({ ...file, file_content: `[Binary file - ${formatFileSize(data.size || file.size_bytes)}]\n\nThis file cannot be displayed as text.` });
          }
        } else {
          console.error('Failed to fetch file content:', response.status, response.statusText);
          setSelectedFile({ ...file, file_content: `Error: ${response.status} ${response.statusText}` });
        }
      } catch (error) {
        console.error('Error fetching file content:', error);
        setSelectedFile({ ...file, file_content: 'Error loading file content' });
      } finally {
        setLoadingContent(false);
      }
    }
  };

  const handleDownload = (file: FileNode) => {
    const blob = new Blob([file.file_content || ''], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = file.file_name;
    link.click();
    URL.revokeObjectURL(url);
  };

  const toggleDirectory = (path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  // Render tree recursively
  const renderTree = (tree: any, path: string = '') => {
    const entries = Object.entries(tree).filter(([key]) => key !== '_files');
    const treeFiles = tree._files || [];

    return (
      <>
        {entries.map(([dirName, subtree]) => {
          const fullPath = path ? `${path}/${dirName}` : dirName;
          const isExpanded = expandedDirs.has(fullPath);

          return (
            <div key={fullPath}>
              <button
                onClick={() => toggleDirectory(fullPath)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-800 rounded transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-400" />
                )}
                {isExpanded ? (
                  <FolderOpen className="w-4 h-4 text-blue-400" />
                ) : (
                  <Folder className="w-4 h-4 text-blue-400" />
                )}
                <span className="text-white">{dirName}</span>
              </button>
              
              {isExpanded && (
                <div className="ml-6">
                  {renderTree(subtree, fullPath)}
                </div>
              )}
            </div>
          );
        })}
        
        {treeFiles.map((file: FileNode) => (
          <button
            key={file.id}
            onClick={() => handleFileClick(file)}
            className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded transition-colors ${
              selectedFile?.id === file.id
                ? 'bg-blue-900/30 border-l-2 border-blue-500'
                : 'hover:bg-gray-800'
            }`}
          >
            <div className="w-4" /> {/* Spacer for alignment */}
            {getFileIcon(file.file_name)}
            <span className="text-white truncate flex-1">{file.file_name}</span>
            <span className="text-xs text-gray-500">{formatFileSize(file.size_bytes)}</span>
          </button>
        ))}
      </>
    );
  };

  const fileTypes = [
    { value: 'all', label: 'All Files' },
    { value: 'code', label: 'Code' },
    { value: 'data', label: 'Data' },
    { value: 'images', label: 'Images' },
    { value: 'logs', label: 'Logs' },
  ];

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading files...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center text-red-400">
          <AlertCircle className="w-12 h-12 mx-auto mb-4" />
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex bg-gray-900">
      {/* Files List/Tree */}
      <div className="flex-1 overflow-auto border-r border-gray-700">
        <div className="p-4">
          <div className="flex items-center gap-2 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <select
              value={fileTypeFilter}
              onChange={(e) => setFileTypeFilter(e.target.value)}
              className="px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {fileTypes.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>

            <div className="flex gap-1 p-1 bg-gray-800 rounded">
              <button
                onClick={() => setViewMode('list')}
                className={`px-2 py-1 text-xs rounded ${
                  viewMode === 'list' ? 'bg-blue-500 text-white' : 'text-gray-400'
                }`}
              >
                List
              </button>
              <button
                onClick={() => setViewMode('tree')}
                className={`px-2 py-1 text-xs rounded ${
                  viewMode === 'tree' ? 'bg-blue-500 text-white' : 'text-gray-400'
                }`}
              >
                Tree
              </button>
            </div>
          </div>

          {filteredFiles.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400">No files generated yet</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {viewMode === 'tree' ? (
                renderTree(fileTree)
              ) : (
                filteredFiles.map(file => (
                  <button
                    key={file.id}
                    onClick={() => handleFileClick(file)}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg transition-colors border ${
                      selectedFile?.id === file.id
                        ? 'bg-blue-900/30 border-blue-700'
                        : 'hover:bg-gray-800 border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    {getFileIcon(file.file_name)}
                    <div className="flex-1 min-w-0 text-left">
                      <p className="text-sm font-medium text-white truncate">
                        {file.file_name}
                      </p>
                      <p className="text-xs text-gray-400 truncate">
                        {file.file_path}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-400">
                        {formatFileSize(file.size_bytes)}
                      </p>
                      {file.agent_name && (
                        <p className="text-xs text-gray-500">
                          {file.agent_name}
                        </p>
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* File Preview/Details */}
      {selectedFile && (
        <div className="w-2/3 overflow-auto bg-gray-800/50">
          <div className="sticky top-0 z-10 p-4 bg-gray-800 border-b border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                {getFileIcon(selectedFile.file_name)}
                <div>
                  <h4 className="text-lg font-semibold text-white">{selectedFile.file_name}</h4>
                  <p className="text-sm text-gray-400">{selectedFile.file_path}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedFile(null)}
                  className="p-2 text-gray-400 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
                {selectedFile.file_content && (
                  <button
                    onClick={() => handleDownload(selectedFile)}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </button>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs text-gray-400">
              <span>Size: {formatFileSize(selectedFile.size_bytes)}</span>
              <span>•</span>
              <span>Node: {selectedFile.node_id}</span>
              {selectedFile.agent_name && (
                <>
                  <span>•</span>
                  <span>Agent: {selectedFile.agent_name}</span>
                </>
              )}
              <span>•</span>
              <span>{new Date(selectedFile.created_at).toLocaleString()}</span>
            </div>
          </div>

          <div className="p-6">
            {loadingContent ? (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-gray-400">Loading file content...</p>
              </div>
            ) : selectedFile.file_content ? (
              <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
                  <span className="text-xs text-gray-400 font-mono">
                    {selectedFile.file_name}
                  </span>
                  <Eye className="w-4 h-4 text-gray-400" />
                </div>
                {selectedFile.content_type === 'image' && selectedFile.encoding === 'base64' ? (
                  <div className="p-4 flex items-center justify-center bg-gray-950">
                    <img 
                      src={`data:${selectedFile.mime_type};base64,${selectedFile.file_content}`}
                      alt={selectedFile.file_name}
                      className="max-w-full max-h-[calc(100vh-300px)] object-contain"
                    />
                  </div>
                ) : (
                  <pre className="p-4 text-sm text-gray-300 overflow-auto max-h-[calc(100vh-300px)] font-mono whitespace-pre-wrap break-words">
                    {selectedFile.file_content}
                  </pre>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>File content not available</p>
                <p className="text-xs mt-2">Content may be too large or binary</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
