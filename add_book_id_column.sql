-- Add book_id column to forum_threads table
-- This migration adds support for linking discussion threads to specific books

ALTER TABLE forum_threads ADD COLUMN IF NOT EXISTS book_id INTEGER;

-- Optional: Create an index for better query performance
CREATE INDEX IF NOT EXISTS idx_forum_threads_book_id ON forum_threads(book_id);

-- Verify the column was added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'forum_threads' 
ORDER BY ordinal_position;
