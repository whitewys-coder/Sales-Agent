CREATE TABLE `migration_stage` (
	`snapshot` text NOT NULL,
	`kind` text NOT NULL,
	`id` text NOT NULL,
	`body` text NOT NULL,
	PRIMARY KEY(`snapshot`, `kind`, `id`)
);
