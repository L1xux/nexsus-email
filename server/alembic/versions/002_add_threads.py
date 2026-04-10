"""Add threads table

Revision ID: 002_add_threads
Revises: 001_initial
Create Date: 2024-04-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '002_add_threads'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'threads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gmail_thread_id', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('participant_count', sa.Integer(), default=1),
        sa.Column('message_count', sa.Integer(), default=1),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('inbox', 'todo', 'waiting', 'done', name='threadstatus'), default='inbox'),
        sa.Column('classification_confidence', sa.Float(), nullable=True),
        sa.Column('classification_reason', sa.String(500), nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('is_read', sa.Boolean(), default=False),
        sa.Column('is_starred', sa.Boolean(), default=False),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gmail_thread_id')
    )
    op.create_index(op.f('ix_threads_category_id'), 'threads', ['category_id'])
    op.create_index(op.f('ix_threads_gmail_thread_id'), 'threads', ['gmail_thread_id'])
    op.create_index(op.f('ix_threads_id'), 'threads', ['id'])
    op.create_index(op.f('ix_threads_is_read'), 'threads', ['is_read'])
    op.create_index(op.f('ix_threads_is_starred'), 'threads', ['is_starred'])
    op.create_index(op.f('ix_threads_last_message_at'), 'threads', ['last_message_at'])
    op.create_index(op.f('ix_threads_status'), 'threads', ['status'])
    op.create_index(op.f('ix_threads_user_id'), 'threads', ['user_id'])
    
    op.add_column('emails', sa.Column('email_thread_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_emails_email_thread_id'), 'emails', ['email_thread_id'])
    op.create_foreign_key(
        'fk_emails_thread_id',
        'emails', 'threads',
        ['email_thread_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_emails_thread_id', 'emails', type_='foreignkey')
    op.drop_index(op.f('ix_emails_email_thread_id'), table_name='emails')
    op.drop_column('emails', 'email_thread_id')
    
    op.drop_table('threads')
