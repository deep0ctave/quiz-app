"""Copy the existing Spring/Flyway data into the Python ORM tables."""

import sqlalchemy as sa
from alembic import op

revision = "0004_import_java_data"
down_revision = "0003_group_created_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    existing = set(sa.inspect(connection).get_table_names())
    if "users" not in existing or "questions" not in existing or "quizzes" not in existing:
        return

    statements = [
        """INSERT INTO py_users (id, name, mobile, pin_hash, email, school, role, active,
                   failed_login_attempts, locked_until, created_at)
           SELECT id, name, mobile, pin_hash, email, school, role, active,
                  failed_login_attempts, locked_until, created_at FROM users
           ON CONFLICT DO NOTHING""",
        """INSERT INTO py_questions (id, text, options_json, correct_option, time_limit_seconds, created_at)
           SELECT id, text, json_build_array(option_a, option_b, option_c, option_d)::text,
                  correct_option, time_limit_seconds, created_at
           FROM questions WHERE deleted_at IS NULL ON CONFLICT DO NOTHING""",
        """INSERT INTO py_quizzes (id, title, total_time_limit_seconds, show_answers, created_at)
           SELECT id, title, total_time_limit_seconds, show_answers, created_at
           FROM quizzes WHERE deleted_at IS NULL ON CONFLICT DO NOTHING""",
        """INSERT INTO py_quiz_questions (quiz_id, position, question_id)
           SELECT qq.quiz_id, qq.position, qq.question_id FROM quiz_questions qq
           JOIN py_quizzes q ON q.id = qq.quiz_id
           JOIN py_questions question ON question.id = qq.question_id
           ON CONFLICT DO NOTHING""",
    ]
    if "student_groups" in existing and "group_members" in existing:
        statements.extend([
            """INSERT INTO py_student_groups (id, name, created_at)
               SELECT id, name, created_at FROM student_groups ON CONFLICT DO NOTHING""",
            """INSERT INTO py_group_members (group_id, student_id)
               SELECT gm.group_id, gm.student_id FROM group_members gm
               JOIN py_student_groups g ON g.id = gm.group_id
               JOIN py_users u ON u.id = gm.student_id ON CONFLICT DO NOTHING""",
        ])
    if "assignments" in existing:
        statements.append(
            """INSERT INTO py_assignments (id, quiz_id, target_type, student_id, group_id,
                       due_at, assigned_by, assigned_at)
               SELECT a.id, a.quiz_id, a.target_type, a.student_id, a.group_id, a.due_at,
                      COALESCE(a.assigned_by, (SELECT id FROM py_users WHERE role = 'ADMIN' ORDER BY id LIMIT 1)),
                      a.assigned_at
               FROM assignments a JOIN py_quizzes q ON q.id = a.quiz_id
               WHERE (a.student_id IS NULL OR EXISTS (SELECT 1 FROM py_users u WHERE u.id = a.student_id))
                 AND (a.group_id IS NULL OR EXISTS (SELECT 1 FROM py_student_groups g WHERE g.id = a.group_id))
               ON CONFLICT DO NOTHING"""
        )
    if "attempts" in existing and "attempt_questions" in existing:
        statements.extend([
            """INSERT INTO py_attempts (id, quiz_id, student_id, quiz_title, total_time_limit_seconds,
                       show_answers, due_at, late, started_at, deadline_at, finished_at, status,
                       finish_reason, score, question_count)
               SELECT a.id, a.quiz_id, a.student_id, a.quiz_title, a.total_time_limit_seconds,
                      a.show_answers, a.due_at, a.late, a.started_at, a.deadline_at, a.finished_at,
                      a.status, a.finish_reason, a.score, a.question_count
               FROM attempts a JOIN py_users u ON u.id = a.student_id
               JOIN py_quizzes q ON q.id = a.quiz_id ON CONFLICT DO NOTHING""",
            """INSERT INTO py_attempt_questions (id, attempt_id, position, question_id, text,
                       options_json, correct_option, time_limit_seconds, served_at, answered_at,
                       selected_option, correct)
               SELECT aq.id, aq.attempt_id, aq.position, aq.question_id, aq.text,
                      json_build_array(aq.option_a, aq.option_b, aq.option_c, aq.option_d)::text,
                      aq.correct_option, aq.time_limit_seconds, aq.served_at, aq.answered_at,
                      aq.selected_option, aq.correct
               FROM attempt_questions aq JOIN py_attempts a ON a.id = aq.attempt_id
               ON CONFLICT DO NOTHING""",
        ])
    for statement in statements:
        connection.execute(sa.text(statement))

    for table_name in ("py_users", "py_questions", "py_quizzes", "py_student_groups", "py_assignments",
                       "py_attempts", "py_attempt_questions"):
        connection.execute(sa.text(
            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {table_name}), 1), "
            f"EXISTS (SELECT 1 FROM {table_name}))"
        ))


def downgrade() -> None:
    pass