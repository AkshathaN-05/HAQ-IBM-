-- Claims can be about unpaid wages or another problem at work.
ALTER TABLE claims ADD COLUMN issue_type TEXT NOT NULL DEFAULT 'wages';
