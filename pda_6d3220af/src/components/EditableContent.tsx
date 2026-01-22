import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Pencil, Check, X } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';

interface EditableContentProps {
  content: string;
  onSave: (newContent: string) => void;
  className?: string;
}

export function EditableContent({ content, onSave, className = '' }: EditableContentProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(content);

  const handleSave = () => {
    onSave(editedContent);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedContent(content);
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <div className={className}>
        <Textarea
          value={editedContent}
          onChange={(e) => setEditedContent(e.target.value)}
          className="min-h-[200px] font-mono text-sm"
        />
        <div className="flex gap-2 mt-2">
          <Button size="sm" onClick={handleSave}>
            <Check className="w-4 h-4 mr-1" />
            Save
          </Button>
          <Button size="sm" variant="outline" onClick={handleCancel}>
            <X className="w-4 h-4 mr-1" />
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative group ${className}`}>
      <MarkdownRenderer content={content} />
      <Button
        size="sm"
        variant="outline"
        className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={() => setIsEditing(true)}
      >
        <Pencil className="w-4 h-4 mr-1" />
        Edit
      </Button>
    </div>
  );
}
