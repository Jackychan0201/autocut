-- run once on Postgres first startup (docker-entrypoint-initdb.d)
CREATE TABLE IF NOT EXISTS Channels (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  link TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS Videos (
  id SERIAL PRIMARY KEY,
  link TEXT UNIQUE NOT NULL,
  is_downloaded BOOLEAN NOT NULL DEFAULT FALSE,
  is_used BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS Shorts (
  id SERIAL PRIMARY KEY,
  num_of_views INTEGER DEFAULT 0,
  num_of_likes INTEGER DEFAULT 0,
  num_of_comments INTEGER DEFAULT 0
);

-- Optional: some helpful index
CREATE INDEX IF NOT EXISTS idx_videos_link ON Videos(link);
