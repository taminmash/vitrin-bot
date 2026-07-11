import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import Json, RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")

INITIAL_RADAR_SOURCES = [
    ("BOE", "Government", "https://www.boe.es/", "official", 5, "Spain", None),
    ("SEPE", "Government", "https://www.sepe.es/", "official", 5, "Spain", None),
    ("Seguridad Social", "Government", "https://www.seg-social.es/", "official", 5, "Spain", None),
    ("Agencia Tributaria", "Government", "https://sede.agenciatributaria.gob.es/", "official", 5, "Spain", None),
    ("Ministerio de Inclusión", "Government", "https://www.inclusion.gob.es/", "official", 5, "Spain", None),
    ("Carrefour", "Discounts", "https://www.carrefour.es/ofertas", "retailer", 4, "Spain", None),
    ("Lidl", "Discounts", "https://www.lidl.es/", "retailer", 4, "Spain", None),
    ("Aldi", "Discounts", "https://www.aldi.es/", "retailer", 4, "Spain", None),
    ("Primor", "Discounts", "https://www.primor.eu/es_es/ofertas", "retailer", 4, "Spain", None),
    ("MediaMarkt", "Discounts", "https://www.mediamarkt.es/", "retailer", 4, "Spain", None),
    ("El Corte Inglés", "Discounts", "https://www.elcorteingles.es/", "retailer", 4, "Spain", None),
    ("InfoJobs", "Jobs", "https://www.infojobs.net/", "jobs", 4, "Spain", None),
    ("Indeed España", "Jobs", "https://es.indeed.com/", "jobs", 4, "Spain", None),
    ("Renfe", "Travel", "https://www.renfe.com/es/es", "travel", 4, "Spain", None),
    ("Ouigo", "Travel", "https://www.ouigo.com/es/", "travel", 4, "Spain", None),
    ("Iryo", "Travel", "https://iryo.eu/es", "travel", 4, "Spain", None),
    ("Iberia", "Travel", "https://www.iberia.com/es/", "travel", 4, "Spain", None),
    ("Ryanair", "Travel", "https://www.ryanair.com/es/es", "travel", 3, "Spain", None),
    ("Eventbrite España", "Events", "https://www.eventbrite.es/", "events", 3, "Spain", None),
    ("Fever", "Events", "https://feverup.com/es", "events", 3, "Spain", None),
    ("Meetup", "Events", "https://www.meetup.com/", "events", 3, "Spain", None),
    ("AEMET", "Weather", "https://www.aemet.es/", "weather", 5, "Spain", None),
]


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def db_cursor(dict_cursor=False):
    conn = get_connection()
    cursor_factory = RealDictCursor if dict_cursor else None
    cur = conn.cursor(cursor_factory=cursor_factory)
    try:
        yield conn, cur
        conn.commit()
    finally:
        cur.close()
        conn.close()


def row_to_dict(row):
    return dict(row) if row else None


def column_exists(cur, table_name, column_name):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def column_data_type(cur, table_name, column_name):
    cur.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    row = cur.fetchone()
    if not row:
        return None
    return row["data_type"] if isinstance(row, dict) else row[0]


def ensure_column(cur, table_name, column_name, column_definition, default_sql=None):
    if not column_exists(cur, table_name, column_name):
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
        return

    if default_sql is not None:
        cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {default_sql}")


def init_db():
    with db_cursor() as (_, cur):
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

        cur.execute("CREATE SEQUENCE IF NOT EXISTS user_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS content_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS message_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS comment_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS draft_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS review_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS publication_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS report_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS reaction_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS admin_log_human_seq")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                display_name TEXT,
                city TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "users", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "users", "human_id", "TEXT")
        ensure_column(cur, "users", "telegram_id", "BIGINT")
        ensure_column(cur, "users", "first_name", "TEXT")
        ensure_column(cur, "users", "status", "TEXT DEFAULT 'active'", "'active'")
        ensure_column(cur, "users", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        if column_data_type(cur, "users", "id") in ("bigint", "integer"):
            cur.execute("UPDATE users SET telegram_id = id WHERE telegram_id IS NULL")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS users_telegram_id_unique
            ON users (telegram_id)
            WHERE telegram_id IS NOT NULL
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                post_type TEXT,
                category TEXT,
                subcategory TEXT,
                display_name TEXT,
                city TEXT,
                content TEXT,
                telegram_id TEXT,
                hashtags TEXT,
                status TEXT DEFAULT 'pending',
                channel_message_id BIGINT,
                approved_by BIGINT,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "posts", "user_id", "BIGINT")
        ensure_column(cur, "posts", "post_type", "TEXT")
        ensure_column(cur, "posts", "category", "TEXT")
        ensure_column(cur, "posts", "subcategory", "TEXT")
        ensure_column(cur, "posts", "display_name", "TEXT")
        ensure_column(cur, "posts", "city", "TEXT")
        ensure_column(cur, "posts", "content", "TEXT")
        ensure_column(cur, "posts", "telegram_id", "TEXT")
        ensure_column(cur, "posts", "hashtags", "TEXT")
        ensure_column(cur, "posts", "status", "TEXT DEFAULT 'pending'", "'pending'")
        ensure_column(cur, "posts", "channel_message_id", "BIGINT")
        ensure_column(cur, "posts", "approved_by", "BIGINT")
        ensure_column(cur, "posts", "approved_at", "TIMESTAMP")
        ensure_column(cur, "posts", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS content_objects (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                user_telegram_id BIGINT NOT NULL,
                content_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                category TEXT,
                city TEXT,
                title TEXT,
                description TEXT,
                price TEXT,
                media_file_id TEXT,
                media_type TEXT,
                anonymous_author TEXT,
                published_channel_id BIGINT,
                published_message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "content_objects", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "content_objects", "human_id", "TEXT")
        ensure_column(cur, "content_objects", "user_telegram_id", "BIGINT")
        ensure_column(cur, "content_objects", "content_type", "TEXT")
        ensure_column(cur, "content_objects", "status", "TEXT DEFAULT 'draft'", "'draft'")
        ensure_column(cur, "content_objects", "category", "TEXT")
        ensure_column(cur, "content_objects", "city", "TEXT")
        ensure_column(cur, "content_objects", "title", "TEXT")
        ensure_column(cur, "content_objects", "description", "TEXT")
        ensure_column(cur, "content_objects", "price", "TEXT")
        ensure_column(cur, "content_objects", "media_file_id", "TEXT")
        ensure_column(cur, "content_objects", "media_type", "TEXT")
        ensure_column(cur, "content_objects", "anonymous_author", "TEXT")
        ensure_column(cur, "content_objects", "published_channel_id", "BIGINT")
        ensure_column(cur, "content_objects", "published_message_id", "BIGINT")
        ensure_column(cur, "content_objects", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "content_objects", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS radar_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content_id UUID REFERENCES content_objects(internal_id),
                title TEXT NOT NULL,
                summary TEXT,
                body TEXT,
                type TEXT NOT NULL,
                category TEXT,
                category_tags JSONB DEFAULT '[]'::jsonb,
                city TEXT,
                province TEXT,
                country TEXT DEFAULT 'Spain',
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                source_url TEXT,
                source_name TEXT,
                urgency TEXT DEFAULT 'low',
                priority_score INTEGER DEFAULT 0,
                audience_tags JSONB DEFAULT '[]'::jsonb,
                is_verified BOOLEAN DEFAULT false,
                is_published BOOLEAN DEFAULT false,
                published_at TIMESTAMP,
                expires_at TIMESTAMP,
                notify_immediately BOOLEAN DEFAULT false,
                daily_digest BOOLEAN DEFAULT true,
                content_status TEXT DEFAULT 'draft',
                channel_status TEXT DEFAULT 'not_sent',
                channel_message_id BIGINT,
                channel_published_at TIMESTAMP,
                last_publish_error TEXT,
                ai_summary TEXT,
                ai_reason TEXT,
                ai_tags JSONB DEFAULT '[]'::jsonb,
                ai_priority INTEGER DEFAULT 0,
                original_text TEXT,
                original_language TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "radar_items", "content_id", "UUID")
        ensure_column(cur, "radar_items", "title", "TEXT")
        ensure_column(cur, "radar_items", "summary", "TEXT")
        ensure_column(cur, "radar_items", "body", "TEXT")
        ensure_column(cur, "radar_items", "type", "TEXT")
        ensure_column(cur, "radar_items", "category", "TEXT")
        ensure_column(cur, "radar_items", "category_tags", "JSONB DEFAULT '[]'::jsonb", "'[]'::jsonb")
        ensure_column(cur, "radar_items", "city", "TEXT")
        ensure_column(cur, "radar_items", "province", "TEXT")
        ensure_column(cur, "radar_items", "country", "TEXT DEFAULT 'Spain'", "'Spain'")
        ensure_column(cur, "radar_items", "start_date", "TIMESTAMP")
        ensure_column(cur, "radar_items", "end_date", "TIMESTAMP")
        ensure_column(cur, "radar_items", "source_url", "TEXT")
        ensure_column(cur, "radar_items", "source_name", "TEXT")
        ensure_column(cur, "radar_items", "urgency", "TEXT DEFAULT 'low'", "'low'")
        ensure_column(cur, "radar_items", "priority_score", "INTEGER DEFAULT 0", "0")
        ensure_column(cur, "radar_items", "audience_tags", "JSONB DEFAULT '[]'::jsonb", "'[]'::jsonb")
        ensure_column(cur, "radar_items", "is_verified", "BOOLEAN DEFAULT false", "false")
        ensure_column(cur, "radar_items", "is_published", "BOOLEAN DEFAULT false", "false")
        ensure_column(cur, "radar_items", "published_at", "TIMESTAMP")
        ensure_column(cur, "radar_items", "expires_at", "TIMESTAMP")
        ensure_column(cur, "radar_items", "notify_immediately", "BOOLEAN DEFAULT false", "false")
        ensure_column(cur, "radar_items", "daily_digest", "BOOLEAN DEFAULT true", "true")
        ensure_column(cur, "radar_items", "content_status", "TEXT DEFAULT 'draft'", "'draft'")
        ensure_column(cur, "radar_items", "channel_status", "TEXT DEFAULT 'not_sent'", "'not_sent'")
        ensure_column(cur, "radar_items", "channel_message_id", "BIGINT")
        ensure_column(cur, "radar_items", "channel_published_at", "TIMESTAMP")
        ensure_column(cur, "radar_items", "last_publish_error", "TEXT")
        ensure_column(cur, "radar_items", "ai_summary", "TEXT")
        ensure_column(cur, "radar_items", "ai_reason", "TEXT")
        ensure_column(cur, "radar_items", "ai_tags", "JSONB DEFAULT '[]'::jsonb", "'[]'::jsonb")
        ensure_column(cur, "radar_items", "ai_priority", "INTEGER DEFAULT 0", "0")
        ensure_column(cur, "radar_items", "original_text", "TEXT")
        ensure_column(cur, "radar_items", "original_language", "TEXT")
        ensure_column(cur, "radar_items", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "radar_items", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        cur.execute(
            """
            UPDATE radar_items
            SET content_status = CASE
                    WHEN content_status IS NOT NULL THEN content_status
                    WHEN channel_status = 'published' THEN 'published'
                    WHEN channel_status = 'ready' THEN 'ready'
                    ELSE 'draft'
                END,
                channel_status = CASE
                    WHEN channel_status = 'published' THEN 'published'
                    WHEN channel_status = 'failed' THEN 'failed'
                    ELSE 'not_sent'
                END
            WHERE content_status IS NULL
               OR channel_status IS NULL
               OR channel_status IN ('draft', 'ready')
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_items_available_idx
            ON radar_items (is_published, published_at, expires_at, type, city)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_items_channel_status_idx
            ON radar_items (channel_status, updated_at)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS radar_raw_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_key TEXT NOT NULL,
                external_id TEXT,
                deduplication_key TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                canonical_url TEXT,
                original_title TEXT NOT NULL,
                original_text TEXT NOT NULL,
                original_language TEXT NOT NULL DEFAULT 'es',
                published_at TIMESTAMP,
                valid_from TIMESTAMP,
                valid_until TIMESTAMP,
                raw_category TEXT,
                raw_location TEXT,
                content_hash TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                ingestion_status TEXT NOT NULL DEFAULT 'raw',
                first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "radar_raw_items", "source_key", "TEXT")
        ensure_column(cur, "radar_raw_items", "external_id", "TEXT")
        ensure_column(cur, "radar_raw_items", "deduplication_key", "TEXT")
        ensure_column(cur, "radar_raw_items", "source_name", "TEXT")
        ensure_column(cur, "radar_raw_items", "source_url", "TEXT")
        ensure_column(cur, "radar_raw_items", "canonical_url", "TEXT")
        ensure_column(cur, "radar_raw_items", "original_title", "TEXT")
        ensure_column(cur, "radar_raw_items", "original_text", "TEXT")
        ensure_column(cur, "radar_raw_items", "original_language", "TEXT DEFAULT 'es'", "'es'")
        ensure_column(cur, "radar_raw_items", "published_at", "TIMESTAMP")
        ensure_column(cur, "radar_raw_items", "valid_from", "TIMESTAMP")
        ensure_column(cur, "radar_raw_items", "valid_until", "TIMESTAMP")
        ensure_column(cur, "radar_raw_items", "raw_category", "TEXT")
        ensure_column(cur, "radar_raw_items", "raw_location", "TEXT")
        ensure_column(cur, "radar_raw_items", "content_hash", "TEXT")
        ensure_column(cur, "radar_raw_items", "metadata", "JSONB NOT NULL DEFAULT '{}'::jsonb", "'{}'::jsonb")
        ensure_column(cur, "radar_raw_items", "ingestion_status", "TEXT NOT NULL DEFAULT 'raw'", "'raw'")
        ensure_column(cur, "radar_raw_items", "first_seen_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "radar_raw_items", "last_seen_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "radar_raw_items", "created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "radar_raw_items", "updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS radar_raw_items_deduplication_key_unique
            ON radar_raw_items (deduplication_key)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_raw_items_source_key_idx
            ON radar_raw_items (source_key)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_raw_items_published_at_idx
            ON radar_raw_items (published_at)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_raw_items_ingestion_status_idx
            ON radar_raw_items (ingestion_status)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_raw_items_source_external_idx
            ON radar_raw_items (source_key, external_id)
            WHERE external_id IS NOT NULL
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS radar_candidates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                raw_item_id UUID NOT NULL REFERENCES radar_raw_items(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL,
                source_name TEXT NOT NULL,
                external_id TEXT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                language TEXT NOT NULL,
                source_url TEXT NOT NULL,
                canonical_url TEXT,
                published_at TIMESTAMP,
                valid_from TIMESTAMP,
                valid_until TIMESTAMP,
                source_category TEXT,
                source_location TEXT,
                country TEXT NOT NULL DEFAULT 'Spain',
                source_type TEXT NOT NULL,
                trust_level INTEGER NOT NULL CHECK (trust_level BETWEEN 1 AND 5),
                candidate_status TEXT NOT NULL DEFAULT 'pending_ai'
                    CHECK (candidate_status IN ('pending_ai', 'rejected', 'failed')),
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
                pipeline_version TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "radar_candidates", "raw_item_id", "UUID")
        ensure_column(cur, "radar_candidates", "source_key", "TEXT")
        ensure_column(cur, "radar_candidates", "source_name", "TEXT")
        ensure_column(cur, "radar_candidates", "external_id", "TEXT")
        ensure_column(cur, "radar_candidates", "title", "TEXT")
        ensure_column(cur, "radar_candidates", "body", "TEXT")
        ensure_column(cur, "radar_candidates", "language", "TEXT")
        ensure_column(cur, "radar_candidates", "source_url", "TEXT")
        ensure_column(cur, "radar_candidates", "canonical_url", "TEXT")
        ensure_column(cur, "radar_candidates", "published_at", "TIMESTAMP")
        ensure_column(cur, "radar_candidates", "valid_from", "TIMESTAMP")
        ensure_column(cur, "radar_candidates", "valid_until", "TIMESTAMP")
        ensure_column(cur, "radar_candidates", "source_category", "TEXT")
        ensure_column(cur, "radar_candidates", "source_location", "TEXT")
        ensure_column(cur, "radar_candidates", "country", "TEXT NOT NULL DEFAULT 'Spain'", "'Spain'")
        ensure_column(cur, "radar_candidates", "source_type", "TEXT")
        ensure_column(cur, "radar_candidates", "trust_level", "INTEGER")
        ensure_column(cur, "radar_candidates", "candidate_status", "TEXT NOT NULL DEFAULT 'pending_ai'", "'pending_ai'")
        ensure_column(cur, "radar_candidates", "metadata", "JSONB NOT NULL DEFAULT '{}'::jsonb", "'{}'::jsonb")
        ensure_column(cur, "radar_candidates", "validation_errors", "JSONB NOT NULL DEFAULT '[]'::jsonb", "'[]'::jsonb")
        ensure_column(cur, "radar_candidates", "pipeline_version", "TEXT")
        ensure_column(cur, "radar_candidates", "created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "radar_candidates", "updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        cur.execute(
            """
            DO $$
            DECLARE constraint_name TEXT;
            BEGIN
                FOR constraint_name IN
                    SELECT con.conname
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    WHERE rel.relname = 'radar_candidates'
                      AND con.contype = 'c'
                      AND pg_get_constraintdef(con.oid) LIKE '%candidate_status%'
                LOOP
                    EXECUTE format('ALTER TABLE radar_candidates DROP CONSTRAINT IF EXISTS %I', constraint_name);
                END LOOP;
            END $$;
            """
        )
        cur.execute(
            """
            UPDATE radar_candidates
            SET candidate_status = 'pending_ai', updated_at = CURRENT_TIMESTAMP
            WHERE candidate_status NOT IN ('pending_ai', 'rejected', 'failed')
            """
        )
        cur.execute(
            """
            ALTER TABLE radar_candidates
            ADD CONSTRAINT radar_candidates_candidate_status_check
            CHECK (candidate_status IN ('pending_ai', 'rejected', 'failed'))
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS radar_candidates_raw_item_unique
            ON radar_candidates (raw_item_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_candidates_status_idx
            ON radar_candidates (candidate_status)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_candidates_source_key_idx
            ON radar_candidates (source_key)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_candidates_published_at_idx
            ON radar_candidates (published_at)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_candidates_created_at_idx
            ON radar_candidates (created_at)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS radar_ai_results (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                candidate_id UUID NOT NULL REFERENCES radar_candidates(id) ON DELETE CASCADE,
                headline TEXT NOT NULL,
                summary TEXT NOT NULL,
                why_it_matters TEXT NOT NULL,
                confidence DOUBLE PRECISION NOT NULL,
                model TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                latency INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "radar_ai_results", "candidate_id", "UUID")
        ensure_column(cur, "radar_ai_results", "headline", "TEXT")
        ensure_column(cur, "radar_ai_results", "summary", "TEXT")
        ensure_column(cur, "radar_ai_results", "why_it_matters", "TEXT")
        ensure_column(cur, "radar_ai_results", "confidence", "DOUBLE PRECISION")
        ensure_column(cur, "radar_ai_results", "model", "TEXT")
        ensure_column(cur, "radar_ai_results", "prompt_version", "TEXT")
        ensure_column(cur, "radar_ai_results", "latency", "INTEGER")
        ensure_column(cur, "radar_ai_results", "created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS radar_ai_results_candidate_unique
            ON radar_ai_results (candidate_id)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS radar_reactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                radar_item_id UUID NOT NULL REFERENCES radar_items(id) ON DELETE CASCADE,
                telegram_user_id BIGINT NOT NULL,
                reaction TEXT NOT NULL CHECK (reaction IN ('like', 'dislike')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (radar_item_id, telegram_user_id)
            )
            """
        )
        ensure_column(cur, "radar_reactions", "id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "radar_reactions", "radar_item_id", "UUID")
        ensure_column(cur, "radar_reactions", "telegram_user_id", "BIGINT")
        ensure_column(cur, "radar_reactions", "reaction", "TEXT")
        ensure_column(cur, "radar_reactions", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "radar_reactions", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS radar_reactions_item_user_unique
            ON radar_reactions (radar_item_id, telegram_user_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS radar_reactions_item_reaction_idx
            ON radar_reactions (radar_item_id, reaction)
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS source_registry (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                category TEXT,
                source_url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                is_active BOOLEAN DEFAULT true,
                trust_level INTEGER DEFAULT 3,
                country TEXT DEFAULT 'Spain',
                city TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "source_registry", "name", "TEXT")
        ensure_column(cur, "source_registry", "category", "TEXT")
        ensure_column(cur, "source_registry", "source_url", "TEXT")
        ensure_column(cur, "source_registry", "source_type", "TEXT")
        ensure_column(cur, "source_registry", "is_active", "BOOLEAN DEFAULT true", "true")
        ensure_column(cur, "source_registry", "trust_level", "INTEGER DEFAULT 3", "3")
        ensure_column(cur, "source_registry", "country", "TEXT DEFAULT 'Spain'", "'Spain'")
        ensure_column(cur, "source_registry", "city", "TEXT")
        ensure_column(cur, "source_registry", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "source_registry", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS source_registry_name_url_unique
            ON source_registry (name, source_url)
            """
        )
        cur.executemany(
            """
            INSERT INTO source_registry (
                name, category, source_url, source_type, trust_level, country, city
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name, source_url) DO NOTHING
            """,
            INITIAL_RADAR_SOURCES,
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS drafts (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                current_step TEXT,
                payload JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "drafts", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "drafts", "human_id", "TEXT")
        ensure_column(cur, "drafts", "content_id", "UUID")
        ensure_column(cur, "drafts", "user_telegram_id", "BIGINT")
        ensure_column(cur, "drafts", "status", "TEXT DEFAULT 'active'", "'active'")
        ensure_column(cur, "drafts", "current_step", "TEXT")
        ensure_column(cur, "drafts", "payload", "JSONB DEFAULT '{}'::jsonb", "'{}'::jsonb")
        ensure_column(cur, "drafts", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "drafts", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                admin_telegram_id BIGINT,
                action TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
            """
        )
        ensure_column(cur, "reviews", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "reviews", "human_id", "TEXT")
        ensure_column(cur, "reviews", "content_id", "UUID")
        ensure_column(cur, "reviews", "admin_telegram_id", "BIGINT")
        ensure_column(cur, "reviews", "action", "TEXT")
        ensure_column(cur, "reviews", "status", "TEXT DEFAULT 'pending'", "'pending'")
        ensure_column(cur, "reviews", "reason", "TEXT")
        ensure_column(cur, "reviews", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "reviews", "resolved_at", "TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS publications (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                channel_id BIGINT NOT NULL,
                channel_message_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "publications", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "publications", "human_id", "TEXT")
        ensure_column(cur, "publications", "content_id", "UUID")
        ensure_column(cur, "publications", "channel_id", "BIGINT")
        ensure_column(cur, "publications", "channel_message_id", "BIGINT")
        ensure_column(cur, "publications", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_review',
                admin_telegram_id BIGINT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            )
            """
        )
        ensure_column(cur, "comments", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "comments", "human_id", "TEXT")
        ensure_column(cur, "comments", "content_id", "UUID")
        ensure_column(cur, "comments", "user_telegram_id", "BIGINT")
        ensure_column(cur, "comments", "body", "TEXT")
        ensure_column(cur, "comments", "status", "TEXT DEFAULT 'pending_review'", "'pending_review'")
        ensure_column(cur, "comments", "admin_telegram_id", "BIGINT")
        ensure_column(cur, "comments", "reason", "TEXT")
        ensure_column(cur, "comments", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "comments", "reviewed_at", "TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reactions (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                reaction TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(content_id, user_telegram_id)
            )
            """
        )
        ensure_column(cur, "reactions", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "reactions", "human_id", "TEXT")
        ensure_column(cur, "reactions", "content_id", "UUID")
        ensure_column(cur, "reactions", "user_telegram_id", "BIGINT")
        ensure_column(cur, "reactions", "reaction", "TEXT")
        ensure_column(cur, "reactions", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "reactions", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS reactions_content_user_unique
            ON reactions (content_id, user_telegram_id)
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            )
            """
        )
        ensure_column(cur, "reports", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "reports", "human_id", "TEXT")
        ensure_column(cur, "reports", "content_id", "UUID")
        ensure_column(cur, "reports", "user_telegram_id", "BIGINT")
        ensure_column(cur, "reports", "reason", "TEXT")
        ensure_column(cur, "reports", "status", "TEXT DEFAULT 'active'", "'active'")
        ensure_column(cur, "reports", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        ensure_column(cur, "reports", "reviewed_at", "TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_logs (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                admin_telegram_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                object_id TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(cur, "admin_logs", "internal_id", "UUID DEFAULT gen_random_uuid()", "gen_random_uuid()")
        ensure_column(cur, "admin_logs", "human_id", "TEXT")
        ensure_column(cur, "admin_logs", "admin_telegram_id", "BIGINT")
        ensure_column(cur, "admin_logs", "action", "TEXT")
        ensure_column(cur, "admin_logs", "object_id", "TEXT")
        ensure_column(cur, "admin_logs", "reason", "TEXT")
        ensure_column(cur, "admin_logs", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")


def next_human_id(cur, prefix, sequence_name):
    cur.execute("SELECT nextval(%s) AS value", (sequence_name,))
    row = cur.fetchone()
    value = row["value"] if isinstance(row, dict) else row[0]
    return f"{prefix}-{value:06d}"


def get_or_create_user(tg_user):
    with db_cursor(dict_cursor=True) as (_, cur):
        id_type = column_data_type(cur, "users", "id")
        has_numeric_id = id_type in ("bigint", "integer")

        cur.execute("SELECT * FROM users WHERE telegram_id = %s", (tg_user.id,))
        row = cur.fetchone()
        legacy_id_match = False
        if not row and has_numeric_id:
            cur.execute("SELECT * FROM users WHERE id = %s", (tg_user.id,))
            row = cur.fetchone()
            legacy_id_match = row is not None

        if row:
            human_id = row.get("human_id") or next_human_id(cur, "USR", "user_human_seq")
            if legacy_id_match:
                where_clause = "id = %s"
            else:
                where_clause = "telegram_id = %s"
            cur.execute(
                f"""
                UPDATE users
                SET human_id = COALESCE(human_id, %s),
                    telegram_id = %s,
                    username = %s,
                    first_name = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE {where_clause}
                RETURNING *
                """,
                (human_id, tg_user.id, tg_user.username, tg_user.first_name, tg_user.id),
            )
            return row_to_dict(cur.fetchone())

        human_id = next_human_id(cur, "USR", "user_human_seq")
        display_name = tg_user.full_name or tg_user.first_name or "کاربر"
        if has_numeric_id:
            cur.execute(
                """
                INSERT INTO users (id, telegram_id, human_id, display_name, username, first_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (tg_user.id, tg_user.id, human_id, display_name, tg_user.username, tg_user.first_name),
            )
        else:
            cur.execute(
                """
                INSERT INTO users (telegram_id, human_id, display_name, username, first_name)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (tg_user.id, human_id, display_name, tg_user.username, tg_user.first_name),
            )
        return row_to_dict(cur.fetchone())


def get_user_profile(user_id):
    with db_cursor() as (_, cur):
        cur.execute("SELECT display_name, city FROM users WHERE telegram_id = %s", (user_id,))
        row = cur.fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
        return None


def save_user_profile(user_id, display_name, city, username=None):
    existing = get_or_create_user(type("TelegramUser", (), {
        "id": user_id,
        "username": username,
        "first_name": display_name,
        "full_name": display_name,
    })())
    with db_cursor() as (_, cur):
        cur.execute(
            """
            UPDATE users
            SET display_name = %s,
                city = %s,
                username = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = %s
            """,
            (display_name, city, username, existing["telegram_id"] or user_id),
        )


def create_content(user_id, content_type):
    with db_cursor(dict_cursor=True) as (_, cur):
        prefix = "MSG" if content_type in ("hayat", "hayat_message") else "CNT"
        sequence = "message_human_seq" if content_type in ("hayat", "hayat_message") else "content_human_seq"
        human_id = next_human_id(cur, prefix, sequence)
        cur.execute(
            """
            INSERT INTO content_objects (human_id, user_telegram_id, content_type, status)
            VALUES (%s, %s, %s, 'draft')
            RETURNING *
            """,
            (human_id, user_id, content_type),
        )
        content = row_to_dict(cur.fetchone())
        draft_id = next_human_id(cur, "DRF", "draft_human_seq")
        cur.execute(
            """
            INSERT INTO drafts (human_id, content_id, user_telegram_id, status, payload)
            VALUES (%s, %s, %s, 'active', '{}'::jsonb)
            """,
            (draft_id, content["internal_id"], user_id),
        )
        return content


def update_content(human_id, **fields):
    allowed = {
        "status",
        "category",
        "city",
        "title",
        "description",
        "price",
        "media_file_id",
        "media_type",
        "anonymous_author",
        "published_channel_id",
        "published_message_id",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_content(human_id)

    assignments = [f"{key} = %s" for key in updates]
    values = list(updates.values())
    values.append(human_id)

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            f"""
            UPDATE content_objects
            SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP
            WHERE human_id = %s
            RETURNING *
            """,
            values,
        )
        return row_to_dict(cur.fetchone())


def update_draft(content_human_id, status=None, current_step=None, payload=None):
    content = get_content(content_human_id)
    if not content:
        return

    fields = []
    values = []
    if status is not None:
        fields.append("status = %s")
        values.append(status)
    if current_step is not None:
        fields.append("current_step = %s")
        values.append(current_step)
    if payload is not None:
        fields.append("payload = %s")
        values.append(Json(payload))

    if not fields:
        return

    values.append(content["internal_id"])
    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            UPDATE drafts
            SET {", ".join(fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE content_id = %s
            """,
            values,
        )


def get_content(human_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT * FROM content_objects WHERE human_id = %s", (human_id,))
        return row_to_dict(cur.fetchone())


def list_user_content(user_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM content_objects
            WHERE user_telegram_id = %s
              AND status <> 'deleted'
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def count_user_content_by_status(user_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM content_objects
            WHERE user_telegram_id = %s
              AND status <> 'deleted'
            GROUP BY status
            """,
            (user_id,),
        )
        return {row["status"]: row["count"] for row in cur.fetchall()}


def available_radar_where():
    return """
        is_published = true
        AND (published_at IS NULL OR published_at <= CURRENT_TIMESTAMP)
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        AND (end_date IS NULL OR end_date > CURRENT_TIMESTAMP)
        AND COALESCE(content_status, 'draft') <> 'expired'
    """


def count_available_radar_by_type():
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            f"""
            SELECT type, COUNT(*) AS count
            FROM radar_items
            WHERE {available_radar_where()}
            GROUP BY type
            """
        )
        return {row["type"]: row["count"] for row in cur.fetchall()}


def count_today_dashboard_items():
    counts = count_available_radar_by_type()
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM content_objects
            WHERE status = 'published'
              AND content_type = 'vitrin_ad'
              AND (category ILIKE %s OR title ILIKE %s OR description ILIKE %s)
            """,
            ("%کار%", "%کار%", "%کار%"),
        )
        job_ads = cur.fetchone()["count"]

    return {
        "jobs": job_ads + counts.get("job", 0),
        "discounts": counts.get("discount", 0),
        "events": counts.get("event", 0),
        "radar": sum(counts.values()),
        "alerts": counts.get("alert", 0),
    }


def list_available_radar_items(radar_type=None, limit=5):
    values = []
    type_clause = ""
    if radar_type and radar_type != "all":
        type_clause = "AND type = %s"
        values.append(radar_type)

    values.append(limit)
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            f"""
            SELECT *
            FROM radar_items
            WHERE {available_radar_where()}
              {type_clause}
            ORDER BY urgency = 'urgent' DESC,
                     priority_score DESC,
                     COALESCE(published_at, created_at) DESC
            LIMIT %s
            """,
            values,
        )
        return [dict(row) for row in cur.fetchall()]


def list_admin_radar_items(limit_per_status=10):
    statuses = ["draft", "ready", "published", "expired", "failed"]
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY CASE
                               WHEN COALESCE(expires_at, end_date) <= CURRENT_TIMESTAMP THEN 'expired'
                               WHEN COALESCE(channel_status, 'not_sent') = 'failed' THEN 'failed'
                               ELSE COALESCE(content_status, 'draft')
                           END
                           ORDER BY COALESCE(ai_priority, priority_score, 0) DESC,
                                    updated_at DESC,
                                    created_at DESC
                       ) AS status_rank
                FROM radar_items
            ) ranked
            WHERE CASE
                    WHEN COALESCE(expires_at, end_date) <= CURRENT_TIMESTAMP THEN 'expired'
                    WHEN COALESCE(channel_status, 'not_sent') = 'failed' THEN 'failed'
                    ELSE COALESCE(content_status, 'draft')
                  END = ANY(%s)
              AND status_rank <= %s
            ORDER BY CASE
                         WHEN COALESCE(expires_at, end_date) <= CURRENT_TIMESTAMP THEN 4
                         WHEN COALESCE(channel_status, 'not_sent') = 'failed' THEN 5
                         WHEN COALESCE(content_status, 'draft') = 'draft' THEN 1
                         WHEN COALESCE(content_status, 'draft') = 'ready' THEN 2
                         WHEN COALESCE(content_status, 'draft') = 'published' THEN 3
                         ELSE 6
                     END,
                     status_rank
            """,
            (statuses, limit_per_status),
        )
        grouped = {status: [] for status in statuses}
        for row in cur.fetchall():
            item = dict(row)
            item.pop("status_rank", None)
            status = radar_content_status(item)
            if item.get("channel_status") == "failed":
                status = "failed"
            grouped[status].append(item)
        return grouped


def radar_content_status(item):
    if item.get("expires_at") and item["expires_at"] <= datetime_now_sql_safe():
        return "expired"
    if item.get("end_date") and item["end_date"] <= datetime_now_sql_safe():
        return "expired"
    return item.get("content_status") or "draft"


def datetime_now_sql_safe():
    from datetime import datetime

    return datetime.now()


def get_radar_item(item_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT * FROM radar_items WHERE id = %s", (item_id,))
        return row_to_dict(cur.fetchone())


def get_active_radar_item(item_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            f"""
            SELECT *
            FROM radar_items
            WHERE id = %s
              AND {available_radar_where()}
            """,
            (item_id,),
        )
        return row_to_dict(cur.fetchone())


def create_radar_item(fields, content_status="draft"):
    allowed = {
        "title",
        "summary",
        "body",
        "type",
        "category",
        "category_tags",
        "city",
        "province",
        "country",
        "start_date",
        "end_date",
        "source_url",
        "source_name",
        "urgency",
        "priority_score",
        "audience_tags",
        "is_verified",
        "is_published",
        "published_at",
        "expires_at",
        "ai_summary",
        "ai_reason",
        "ai_tags",
        "ai_priority",
        "original_text",
        "original_language",
    }
    payload = {key: value for key, value in fields.items() if key in allowed}
    payload.setdefault("country", "Spain")
    payload.setdefault("type", "alert")
    payload.setdefault("category", payload["type"])
    payload.setdefault("category_tags", [])
    payload.setdefault("urgency", "low")
    payload.setdefault("priority_score", 0)
    payload.setdefault("audience_tags", [])
    payload.setdefault("ai_tags", [])
    payload.setdefault("is_verified", True)
    payload.setdefault("is_published", content_status in ("ready", "published"))
    payload["content_status"] = content_status
    payload["channel_status"] = "not_sent"

    columns = list(payload.keys())
    values = [
        Json(payload[column]) if column in ("audience_tags", "ai_tags", "category_tags") else payload[column]
        for column in columns
    ]
    placeholders = ", ".join(["%s"] * len(columns))

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            f"""
            INSERT INTO radar_items ({", ".join(columns)})
            VALUES ({placeholders})
            RETURNING *
            """,
            values,
        )
        return row_to_dict(cur.fetchone())


def update_radar_content_status(item_id, content_status):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_items
            SET content_status = %s,
                is_published = CASE WHEN %s IN ('ready', 'published') THEN true ELSE is_published END,
                published_at = CASE
                    WHEN %s IN ('ready', 'published') THEN COALESCE(published_at, CURRENT_TIMESTAMP)
                    ELSE published_at
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (content_status, content_status, content_status, item_id),
        )
        return row_to_dict(cur.fetchone())


def list_source_registry(active_only=True):
    where_clause = "WHERE is_active = true" if active_only else ""
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            f"""
            SELECT *
            FROM source_registry
            {where_clause}
            ORDER BY category, trust_level DESC, name
            """
        )
        return [dict(row) for row in cur.fetchall()]


def mark_radar_channel_published(item_id, message_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_items
            SET content_status = 'published',
                channel_status = 'published',
                channel_message_id = %s,
                channel_published_at = CURRENT_TIMESTAMP,
                last_publish_error = NULL,
                is_published = true,
                published_at = COALESCE(published_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (message_id, item_id),
        )
        return row_to_dict(cur.fetchone())


def mark_radar_channel_failed(item_id, error_text=None):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_items
            SET channel_status = 'failed',
                last_publish_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (error_text, item_id),
        )
        return row_to_dict(cur.fetchone())


def save_radar_reaction(item_id, user_id, reaction):
    if reaction not in ("like", "dislike"):
        raise ValueError("Invalid Radar reaction")

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            INSERT INTO radar_reactions (radar_item_id, telegram_user_id, reaction)
            VALUES (%s, %s, %s)
            ON CONFLICT (radar_item_id, telegram_user_id) DO UPDATE
            SET reaction = EXCLUDED.reaction,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (item_id, user_id, reaction),
        )
        return row_to_dict(cur.fetchone())


def count_radar_reactions(item_id):
    counts = {"like": 0, "dislike": 0}
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT reaction, COUNT(*) AS count
            FROM radar_reactions
            WHERE radar_item_id = %s
            GROUP BY reaction
            """,
            (item_id,),
        )
        for row in cur.fetchall():
            if row["reaction"] in counts:
                counts[row["reaction"]] = row["count"]
    return counts


def list_pending_content():
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM content_objects
            WHERE status = 'pending_review'
            ORDER BY updated_at ASC
            LIMIT 20
            """
        )
        return [dict(row) for row in cur.fetchall()]


def submit_for_review(content_human_id):
    content = update_content(content_human_id, status="pending_review")
    update_draft(content_human_id, status="pending_review")
    with db_cursor(dict_cursor=True) as (_, cur):
        review_id = next_human_id(cur, "REV", "review_human_seq")
        cur.execute(
            """
            INSERT INTO reviews (human_id, content_id, action, status)
            VALUES (%s, %s, 'submit', 'pending')
            RETURNING *
            """,
            (review_id, content["internal_id"]),
        )
        return content, row_to_dict(cur.fetchone())


def resolve_review(content_human_id, admin_id, action, reason=None):
    status_by_action = {
        "approve": "published",
        "need_edit": "needs_edit",
        "reject": "rejected",
        "delete": "deleted",
    }
    content_status = status_by_action[action]
    content = update_content(content_human_id, status=content_status)
    if action == "approve":
        update_draft(content_human_id, status="published")
    elif action == "need_edit":
        update_draft(content_human_id, status="needs_edit")
    elif action in ("reject", "delete"):
        update_draft(content_human_id, status=content_status)

    with db_cursor(dict_cursor=True) as (_, cur):
        review_status = "approved" if action == "approve" else action
        cur.execute(
            """
            UPDATE reviews
            SET admin_telegram_id = %s,
                action = %s,
                status = %s,
                reason = %s,
                resolved_at = CURRENT_TIMESTAMP
            WHERE content_id = %s
              AND status = 'pending'
            """,
            (admin_id, action, review_status, reason, content["internal_id"]),
        )
        log_admin_action(admin_id, action, content_human_id, reason, cur=cur)
        return content


def save_publication(content_human_id, channel_id, message_id):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "PUB", "publication_human_seq")
        cur.execute(
            """
            INSERT INTO publications (human_id, content_id, channel_id, channel_message_id)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (human_id, content["internal_id"], channel_id, message_id),
        )
        publication = row_to_dict(cur.fetchone())
        cur.execute(
            """
            UPDATE content_objects
            SET status = 'published',
                published_channel_id = %s,
                published_message_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE internal_id = %s
            """,
            (channel_id, message_id, content["internal_id"]),
        )
        return publication


def archive_content(content_human_id, user_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE content_objects
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE human_id = %s
              AND user_telegram_id = %s
              AND status IN ('draft', 'needs_edit')
            RETURNING *
            """,
            (content_human_id, user_id),
        )
        return row_to_dict(cur.fetchone())


def create_comment(content_human_id, user_id, body):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "COM", "comment_human_seq")
        cur.execute(
            """
            INSERT INTO comments (human_id, content_id, user_telegram_id, body, status)
            VALUES (%s, %s, %s, %s, 'pending_review')
            RETURNING *
            """,
            (human_id, content["internal_id"], user_id, body),
        )
        comment = row_to_dict(cur.fetchone())
        comment["content_human_id"] = content_human_id
        return comment


def get_comment(human_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT c.*, co.human_id AS content_human_id
            FROM comments c
            JOIN content_objects co ON co.internal_id = c.content_id
            WHERE c.human_id = %s
            """,
            (human_id,),
        )
        return row_to_dict(cur.fetchone())


def list_pending_comments(limit=20):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT c.*, co.human_id AS content_human_id, co.title AS content_title
            FROM comments c
            JOIN content_objects co ON co.internal_id = c.content_id
            WHERE c.status = 'pending_review'
            ORDER BY c.created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def resolve_comment(comment_human_id, admin_id, action, reason=None):
    status = "approved" if action == "approve" else "rejected"
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE comments
            SET status = %s,
                admin_telegram_id = %s,
                reason = %s,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE human_id = %s
            RETURNING *
            """,
            (status, admin_id, reason, comment_human_id),
        )
        comment = row_to_dict(cur.fetchone())
        log_admin_action(admin_id, f"comment_{action}", comment_human_id, reason, cur=cur)
        return comment


def list_approved_comments(content_human_id):
    content = get_content(content_human_id)
    if not content:
        return []
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM comments
            WHERE content_id = %s
              AND status = 'approved'
            ORDER BY created_at ASC
            LIMIT 20
            """,
            (content["internal_id"],),
        )
        return [dict(row) for row in cur.fetchall()]


def save_reaction(content_human_id, user_id, reaction):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "RCT", "reaction_human_seq")
        cur.execute(
            """
            INSERT INTO reactions (human_id, content_id, user_telegram_id, reaction)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (content_id, user_telegram_id) DO UPDATE
            SET reaction = EXCLUDED.reaction,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (human_id, content["internal_id"], user_id, reaction),
        )
        return row_to_dict(cur.fetchone())


def count_reactions(content_human_id):
    content = get_content(content_human_id)
    if not content:
        return {"like": 0, "dislike": 0}
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT reaction, COUNT(*) AS count
            FROM reactions
            WHERE content_id = %s
            GROUP BY reaction
            """,
            (content["internal_id"],),
        )
        counts = {"like": 0, "dislike": 0}
        for row in cur.fetchall():
            counts[row["reaction"]] = row["count"]
        return counts


def create_report(content_human_id, user_id, reason):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "RPT", "report_human_seq")
        cur.execute(
            """
            INSERT INTO reports (human_id, content_id, user_telegram_id, reason, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING *
            """,
            (human_id, content["internal_id"], user_id, reason),
        )
        return row_to_dict(cur.fetchone())


def list_active_reports():
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT r.*, co.human_id AS content_human_id, co.content_type, co.title
            FROM reports r
            JOIN content_objects co ON co.internal_id = r.content_id
            WHERE r.status = 'active'
            ORDER BY r.created_at ASC
            LIMIT 20
            """
        )
        return [dict(row) for row in cur.fetchall()]


def log_admin_action(admin_id, action, object_id, reason=None, cur=None):
    if cur is not None:
        human_id = next_human_id(cur, "LOG", "admin_log_human_seq")
        cur.execute(
            """
            INSERT INTO admin_logs (human_id, admin_telegram_id, action, object_id, reason)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (human_id, admin_id, action, object_id, reason),
        )
        return

    with db_cursor() as (_, own_cur):
        log_admin_action(admin_id, action, object_id, reason, cur=own_cur)
