-- Persist provider usage anchors for hybrid context token estimation
-- (deepy last_usage_tokens / last_usage_record_count; pi estimateContextTokens).

ALTER TABLE sessions ADD COLUMN last_usage_tokens INTEGER;
ALTER TABLE sessions ADD COLUMN last_usage_message_count INTEGER;
