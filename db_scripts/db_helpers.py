from db_scripts.db_connect import db_conn

def fetch_channels():
    """Return all channels from DB."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, link FROM Channels ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def video_exists(link):
    """Check if video already exists in DB."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM Videos WHERE link = %s LIMIT 1;", (link,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists

def count_undownloaded_videos():
    """Return number of videos not yet downloaded."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Videos WHERE is_downloaded = FALSE;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
