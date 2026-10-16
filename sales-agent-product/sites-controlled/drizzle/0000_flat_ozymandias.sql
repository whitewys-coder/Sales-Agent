CREATE TABLE `records` (
	`kind` text NOT NULL,
	`id` text NOT NULL,
	`body` text NOT NULL,
	PRIMARY KEY(`kind`, `id`)
);
