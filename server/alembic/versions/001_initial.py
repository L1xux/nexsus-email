"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-04-07 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('google_access_token', sa.Text(), nullable=True),
        sa.Column('google_refresh_token', sa.Text(), nullable=True),
        sa.Column('google_token_expiry', sa.DateTime(), nullable=True),
        sa.Column('picture', sa.String(512), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'])
    op.create_index(op.f('ix_users_id'), 'users', ['id'])

    # Create categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('color', sa.String(7), default='#6366F1'),
        sa.Column('is_system', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_categories_id'), 'categories', ['id'])
    op.create_index(op.f('ix_categories_user_id'), 'categories', ['user_id'])

    # Create emails table
    op.create_table(
        'emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gmail_message_id', sa.String(255), nullable=False),
        sa.Column('history_id', sa.String(255), nullable=True),
        sa.Column('thread_id', sa.String(255), nullable=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('sender', sa.String(255), nullable=True),
        sa.Column('sender_email', sa.String(255), nullable=True),
        sa.Column('recipients', sa.Text(), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('label_ids', sa.Text(), nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('inbox', 'todo', 'waiting', 'done', name='emailstatus'), default='inbox'),
    sa.Column('classification_confidence', sa.Float(), nullable=True),
    sa.Column('classification_reason', sa.String(500), nullable=True),
    sa.Column('is_read', sa.Boolean(), default=False),
        sa.Column('is_starred', sa.Boolean(), default=False),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('synced_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gmail_message_id')
    )
    op.create_index(op.f('ix_emails_category_id'), 'emails', ['category_id'])
    op.create_index(op.f('ix_emails_gmail_message_id'), 'emails', ['gmail_message_id'])
    op.create_index(op.f('ix_emails_history_id'), 'emails', ['history_id'])
    op.create_index(op.f('ix_emails_id'), 'emails', ['id'])
    op.create_index(op.f('ix_emails_is_read'), 'emails', ['is_read'])
    op.create_index(op.f('ix_emails_is_starred'), 'emails', ['is_starred'])
    op.create_index(op.f('ix_emails_received_at'), 'emails', ['received_at'])
    op.create_index(op.f('ix_emails_sender_email'), 'emails', ['sender_email'])
    op.create_index(op.f('ix_emails_status'), 'emails', ['status'])
    op.create_index(op.f('ix_emails_thread_id'), 'emails', ['thread_id'])
    op.create_index(op.f('ix_emails_user_id'), 'emails', ['user_id'])

    # Create feedback table
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.Integer(), nullable=True),
        sa.Column('original_category', sa.String(100), nullable=True),
        sa.Column('corrected_category', sa.String(100), nullable=False),
        sa.Column('user_comment', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('vector_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['email_id'], ['emails.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feedback_id'), 'feedback', ['id'])
    op.create_index(op.f('ix_feedback_user_id'), 'feedback', ['user_id'])


def downgrade() -> None:
    op.drop_table('feedback')
    op.drop_table('emails')
    op.drop_table('categories')
    op.drop_table('users')
