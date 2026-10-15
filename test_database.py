from database.connection import get_connection


def test_database():
    conn = None

    try:
        conn = get_connection()

        with conn.cursor() as cur:
            cur.execute("""
                SELECT current_database(), current_user;
            """)
            print("Database:", cur.fetchone())

            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'users'
                ORDER BY ordinal_position;
            """)

            print("\nCấu trúc bảng users:")
            for row in cur.fetchall():
                print(row)

            cur.execute("""
                SELECT id, username, role
                FROM public.users
                ORDER BY id DESC
                LIMIT 10;
            """)

            print("\nTài khoản hiện có:")
            for row in cur.fetchall():
                print(row)

        print("\nKết nối PostgreSQL thành công!")

    except Exception as exc:
        print("Lỗi kết nối hoặc truy vấn:", exc)

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    test_database()