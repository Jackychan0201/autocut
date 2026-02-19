from db_scripts.db_connect import db_conn
import logging

logger = logging.getLogger("DB_insert")

def db_insert_video(link, channel_id):
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO Videos (link, is_downloaded, is_used, channel_id)
            VALUES (%s, FALSE, FALSE, %s)
            ON CONFLICT (link) DO NOTHING
            RETURNING id;
            """,
            (link, channel_id),
        )
        res = cur.fetchone()
        conn.commit()
        if res:
            vid_id = res[0]
            logger.info("Inserted video id=%s link=%s channel_id=%s", vid_id, link, channel_id)
            return vid_id
        else:
            logger.info("Video already existed (race): %s", link)
            return None
    finally:
        cur.close()
        conn.close()

def db_insert_channel(channels: list[dict]):
    conn = db_conn()
    cur = conn.cursor()
    query = """
        INSERT INTO channels (name, link)
        VALUES (%s, %s)
        ON CONFLICT (name) DO NOTHING;
        """
    for ch in channels:
        cur.execute(query, (ch["title"], ch["url"]))

    conn.commit()
    cur.close()
    conn.close()

    print(f"Inserted {len(channels)} channels into the database.")
