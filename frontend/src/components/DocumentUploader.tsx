import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Upload,
  FileText,
  FileType2,
  AlertCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import { uploadSourceFile, getSourceFiles } from '../api/projects';
import type { SourceDocument } from '../types';

interface DocumentUploaderProps {
  projectId: string;
  onUploadComplete?: () => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const ACCEPTED_TYPES = ['.pdf', '.docx', '.txt'];


function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function fileTypeIcon(fileType: string) {
  switch (fileType) {
    case 'pdf':
      return <FileText className="w-4 h-4 text-rose-400" />;
    case 'docx':
      return <FileType2 className="w-4 h-4 text-blue-400" />;
    default:
      return <FileText className="w-4 h-4 text-slate-400" />;
  }
}

export default function DocumentUploader({ projectId, onUploadComplete }: DocumentUploaderProps) {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    try {
      const docs = await getSourceFiles(projectId);
      setDocuments(docs);
    } catch {
      // Silently ignore – documents list may be empty
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `File "${file.name}" exceeds the 10 MB limit (${formatBytes(file.size)}).`;
    }
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED_TYPES.includes(ext)) {
      return `Unsupported file type "${ext}". Allowed: PDF, DOCX, TXT.`;
    }
    return null;
  };

  const handleUpload = async (file: File) => {
    const error = validateFile(file);
    if (error) {
      setUploadError(error);
      return;
    }

    setUploadError(null);
    setIsUploading(true);
    try {
      await uploadSourceFile(projectId, file);
      await fetchDocuments();
      onUploadComplete?.();
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
    // Reset input so re-selecting same file triggers onChange
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Drop Zone */}
      <div
        id="document-drop-zone"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center gap-3 p-8 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200 ${
          isDragging
            ? 'border-cyan-500 bg-cyan-950/30 shadow-[0_0_30px_-10px_rgba(6,182,212,0.3)]'
            : 'border-slate-700/80 bg-slate-900/30 hover:border-slate-600 hover:bg-slate-900/50'
        }`}
      >
        {isUploading ? (
          <RefreshCw className="w-8 h-8 text-brand-400 animate-spin" />
        ) : (
          <Upload className={`w-8 h-8 ${isDragging ? 'text-cyan-400' : 'text-slate-500'}`} />
        )}
        <div className="text-center">
          <p className={`text-sm font-medium ${isDragging ? 'text-cyan-300' : 'text-slate-300'}`}>
            {isUploading ? 'Uploading & Parsing...' : 'Drop files here or click to browse'}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Supported: PDF, DOCX, TXT — Max 10 MB
          </p>
        </div>
        <input
          ref={fileInputRef}
          id="file-input"
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Upload Error */}
      {uploadError && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-950/50 border border-rose-500/30 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span className="flex-1">{uploadError}</span>
          <button onClick={() => setUploadError(null)} className="text-rose-400 hover:text-rose-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Uploaded Documents List */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Source Documents ({documents.length})
          </h4>
          <button
            onClick={fetchDocuments}
            disabled={isLoading}
            className="text-slate-500 hover:text-slate-300 transition p-0.5"
            title="Refresh document list"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {isLoading && documents.length === 0 ? (
          <div className="p-4 text-center text-slate-500 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1 text-brand-400" />
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="p-4 text-center text-slate-600 text-xs rounded-lg border border-dashed border-slate-800">
            No source documents uploaded yet.
          </div>
        ) : (
          <div className="space-y-1.5">
            {documents.map((doc) => (
              <div
                key={doc.id}
                id={`source-doc-${doc.id}`}
                className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-900/50 border border-slate-800/60 group hover:border-slate-700 transition"
              >
                {fileTypeIcon(doc.file_type)}
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-200 truncate">
                    {doc.filename}
                  </p>
                  <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-0.5">
                    <span className="uppercase font-semibold">{doc.file_type}</span>
                    {doc.file_size_bytes && (
                      <>
                        <span>•</span>
                        <span>{formatBytes(doc.file_size_bytes)}</span>
                      </>
                    )}
                    <span>•</span>
                    <span>{doc.chunk_count} chunks</span>
                  </div>
                </div>
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                    doc.status === 'READY'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : doc.status === 'FAILED'
                      ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  }`}
                >
                  {doc.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
