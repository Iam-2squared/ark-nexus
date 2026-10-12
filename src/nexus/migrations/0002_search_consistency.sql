CREATE TRIGGER IF NOT EXISTS conversations_fts_au AFTER UPDATE OF title ON conversations
WHEN old.title != new.title BEGIN
  UPDATE message_search SET title=new.title
  WHERE message_id IN (SELECT id FROM messages WHERE conversation_id=new.id);
END;
CREATE TRIGGER IF NOT EXISTS messages_fts_ad AFTER DELETE ON messages BEGIN
  DELETE FROM message_search WHERE message_id=old.id;
END;
CREATE TRIGGER IF NOT EXISTS messages_fts_au AFTER UPDATE OF content ON messages BEGIN
  UPDATE message_search SET content=new.content WHERE message_id=new.id;
END;
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS conversations_project ON conversations(project_id);
CREATE INDEX IF NOT EXISTS import_batches_source ON import_batches(source_id);
