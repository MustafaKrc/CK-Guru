// frontend/components/commits/FileDiffViewer.tsx
import React from 'react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '../ui/scroll-area';

interface FileDiffViewerProps {
  diffText: string;
}

export const FileDiffViewer: React.FC<FileDiffViewerProps> = ({ diffText }) => {
  if (!diffText) {
    return <p className="text-xs text-muted-foreground italic">No diff content available for this file.</p>;
  }

  const lines = diffText.split('\n');

  const getLineClass = (line: string) => {
    if (line.startsWith('+')) return 'bg-green-600/10 text-green-800 dark:text-green-300';
    if (line.startsWith('-')) return 'bg-red-600/10 text-red-800 dark:text-red-300';
    if (line.startsWith('@@')) return 'bg-blue-600/10 text-blue-800 dark:text-blue-300 font-semibold';
    return 'text-muted-foreground';
  };

  return (
    <ScrollArea className="max-h-[400px] font-mono text-xs border rounded-md bg-muted/30">
      <div className="p-2">
        {lines.map((line, index) => (
          <div key={index} className={cn('whitespace-pre-wrap break-words w-full', getLineClass(line))}>
            <span className={cn('inline-block w-8 select-none text-right pr-2 opacity-50', { 'border-r': true })}>{index + 1}</span>
            <span className={cn('pl-2')}>{line || ' '}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};