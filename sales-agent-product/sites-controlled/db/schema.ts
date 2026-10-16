import { sqliteTable, text, primaryKey } from 'drizzle-orm/sqlite-core';
export const records = sqliteTable('records', {
  kind: text('kind').notNull(), id: text('id').notNull(), body: text('body').notNull(),
}, t => [primaryKey({ columns: [t.kind, t.id] })]);
export const migrationStage = sqliteTable('migration_stage', {
 snapshot: text('snapshot').notNull(), kind: text('kind').notNull(), id:text('id').notNull(), body:text('body').notNull(),
},t=>[primaryKey({columns:[t.snapshot,t.kind,t.id]})]);
export const paidRequests=sqliteTable('paid_requests',{
 id:text('id').primaryKey(), body:text('body').notNull(),
});
