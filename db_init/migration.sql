ALTER TABLE channels ADD CONSTRAINT channels_name_key UNIQUE (name);
ALTER TABLE videos
ADD COLUMN channel_id INT;
ALTER TABLE videos
ADD CONSTRAINT videos_channel_id_fkey
FOREIGN KEY (channel_id)
REFERENCES channels(id)
ON DELETE CASCADE;

CREATE INDEX idx_videos_channel_id ON videos(channel_id);
