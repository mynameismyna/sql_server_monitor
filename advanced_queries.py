"""
Gelişmiş SQL Server diagnostik sorguları.

Tüm sorgular yalnızca read-only SELECT / CTE ifadeleridir.
EXEC, DBCC, DDL ve veri değiştiren komutlar kullanılmaz.
"""

ADVANCED_QUERIES = {
    "=== SUNUCU SAĞLIK ÖZETİ ===": "",

    "Sunucu Anlık Durum Kartı": """
        SELECT
            SERVERPROPERTY('ServerName') AS server_name,
            SERVERPROPERTY('ProductVersion') AS product_version,
            SERVERPROPERTY('ProductLevel') AS product_level,
            SERVERPROPERTY('Edition') AS edition,
            @@VERSION AS full_version,
            (SELECT cpu_count FROM sys.dm_os_sys_info) AS logical_cpu_count,
            (SELECT physical_memory_kb / 1024 / 1024 FROM sys.dm_os_sys_info) AS physical_memory_gb,
            (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process = 1) AS user_sessions,
            (SELECT COUNT(*) FROM sys.dm_exec_requests WHERE session_id > 50) AS active_requests,
            (SELECT COUNT(*) FROM sys.dm_exec_requests WHERE blocking_session_id <> 0) AS blocked_requests,
            (SELECT COUNT(*) FROM sys.databases WHERE state_desc <> 'ONLINE') AS offline_or_suspect_dbs,
            SYSDATETIME() AS checked_at
    """,

    "Page Life Expectancy ve Buffer Hit": """
        SELECT
            object_name,
            counter_name,
            instance_name,
            cntr_value,
            CASE
                WHEN counter_name = 'Page life expectancy' AND cntr_value < 300 THEN 'Düşük - bellek baskısı olabilir'
                WHEN counter_name = 'Buffer cache hit ratio' AND cntr_value < 95 THEN 'Düşük - disk I/O artışı mümkün'
                ELSE 'Normal / İzle'
            END AS status_hint
        FROM sys.dm_os_performance_counters
        WHERE
            (object_name LIKE '%Buffer Manager%' AND counter_name IN ('Page life expectancy', 'Buffer cache hit ratio'))
            OR (object_name LIKE '%Memory Manager%' AND counter_name IN ('Total Server Memory (KB)', 'Target Server Memory (KB)', 'Memory Grants Pending'))
        ORDER BY object_name, counter_name
    """,

    "Scheduler ve Runnable Task Yoğunluğu": """
        SELECT
            scheduler_id,
            cpu_id,
            status,
            current_tasks_count,
            runnable_tasks_count,
            current_workers_count,
            active_workers_count,
            work_queue_count,
            pending_disk_io_count,
            load_factor,
            yield_count,
            CASE
                WHEN runnable_tasks_count > 5 THEN 'CPU kuyruğu yüksek'
                WHEN pending_disk_io_count > 10 THEN 'Disk I/O bekliyor'
                ELSE 'Normal'
            END AS pressure_hint
        FROM sys.dm_os_schedulers
        WHERE status = 'VISIBLE ONLINE'
        ORDER BY runnable_tasks_count DESC, pending_disk_io_count DESC
    """,

    "Memory Grant Bekleyen Sorgular": """
        SELECT
            r.session_id,
            r.status,
            r.command,
            r.wait_type,
            r.wait_time,
            r.granted_query_memory,
            mg.requested_memory_kb,
            mg.granted_memory_kb,
            mg.required_memory_kb,
            mg.used_memory_kb,
            mg.max_used_memory_kb,
            mg.dop,
            DB_NAME(r.database_id) AS database_name,
            SUBSTRING(t.text, (r.statement_start_offset / 2) + 1,
                ((CASE r.statement_end_offset
                    WHEN -1 THEN DATALENGTH(t.text)
                    ELSE r.statement_end_offset
                END - r.statement_start_offset) / 2) + 1) AS statement_text
        FROM sys.dm_exec_requests r
        LEFT JOIN sys.dm_exec_query_memory_grants mg ON r.session_id = mg.session_id AND r.request_id = mg.request_id
        CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
        WHERE r.session_id > 50
          AND (
                r.wait_type LIKE 'RESOURCE_SEMAPHORE%'
                OR mg.grant_time IS NULL
                OR mg.requested_memory_kb > 0
          )
        ORDER BY mg.requested_memory_kb DESC, r.wait_time DESC
    """,

    "Pending Disk I/O İstekleri": """
        SELECT
            DB_NAME(mf.database_id) AS database_name,
            mf.name AS logical_file_name,
            mf.physical_name,
            vfs.io_stall_read_ms,
            vfs.io_stall_write_ms,
            vfs.num_of_reads,
            vfs.num_of_writes,
            CAST(vfs.io_stall_read_ms * 1.0 / NULLIF(vfs.num_of_reads, 0) AS DECIMAL(12, 2)) AS avg_read_ms,
            CAST(vfs.io_stall_write_ms * 1.0 / NULLIF(vfs.num_of_writes, 0) AS DECIMAL(12, 2)) AS avg_write_ms,
            vfs.size_on_disk_bytes / 1024 / 1024 AS size_on_disk_mb
        FROM sys.dm_io_virtual_file_stats(NULL, NULL) vfs
        INNER JOIN sys.master_files mf ON vfs.database_id = mf.database_id AND vfs.file_id = mf.file_id
        ORDER BY (vfs.io_stall_read_ms + vfs.io_stall_write_ms) DESC
    """,

    "=== PERFORMANS DERİN ANALİZ ===": "",

    "Ad-hoc Plan Cache Şişmesi": """
        SELECT
            objtype,
            COUNT(*) AS plan_count,
            SUM(size_in_bytes) / 1024 / 1024 AS total_size_mb,
            AVG(usecounts) AS avg_use_counts,
            SUM(CASE WHEN usecounts = 1 THEN 1 ELSE 0 END) AS single_use_plans,
            CAST(100.0 * SUM(CASE WHEN usecounts = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 2)) AS single_use_pct
        FROM sys.dm_exec_cached_plans
        GROUP BY objtype
        ORDER BY total_size_mb DESC
    """,

    "Tek Kullanımlık Pahalı Planlar": """
        SELECT TOP 30
            cp.objtype,
            cp.usecounts,
            cp.size_in_bytes / 1024.0 AS size_kb,
            qs.execution_count,
            qs.total_worker_time / 1000.0 AS total_cpu_ms,
            qs.total_elapsed_time / 1000.0 AS total_elapsed_ms,
            qs.total_logical_reads,
            SUBSTRING(st.text, (qs.statement_start_offset / 2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(st.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset) / 2) + 1) AS statement_text
        FROM sys.dm_exec_cached_plans cp
        INNER JOIN sys.dm_exec_query_stats qs ON cp.plan_handle = qs.plan_handle
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
        WHERE cp.usecounts = 1
          AND cp.objtype IN ('Adhoc', 'Prepared')
        ORDER BY qs.total_worker_time DESC
    """,

    "Yüksek Compile / Recompile Oranı": """
        SELECT
            counter_name,
            cntr_value,
            CASE
                WHEN counter_name = 'SQL Compilations/sec' THEN 'Derleme yoğunluğu'
                WHEN counter_name = 'SQL Re-Compilations/sec' THEN 'Yeniden derleme yoğunluğu'
                WHEN counter_name = 'Batch Requests/sec' THEN 'İş yükü referansı'
                ELSE counter_name
            END AS meaning
        FROM sys.dm_os_performance_counters
        WHERE object_name LIKE '%SQL Statistics%'
          AND counter_name IN ('SQL Compilations/sec', 'SQL Re-Compilations/sec', 'Batch Requests/sec', 'Auto-Param Attempts/sec')
        ORDER BY counter_name
    """,

    "Parameter Sniffing Adayları": """
        SELECT TOP 25
            qs.query_hash,
            COUNT(*) AS plan_variants,
            SUM(qs.execution_count) AS total_executions,
            MAX(qs.max_worker_time) / 1000.0 AS max_cpu_ms,
            MIN(qs.min_worker_time) / 1000.0 AS min_cpu_ms,
            CAST(MAX(qs.max_worker_time) * 1.0 / NULLIF(MIN(NULLIF(qs.min_worker_time, 0)), 0) AS DECIMAL(12, 2)) AS cpu_variance_ratio,
            MAX(qs.max_logical_reads) AS max_logical_reads,
            MIN(qs.min_logical_reads) AS min_logical_reads,
            MAX(SUBSTRING(st.text, (qs.statement_start_offset / 2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(st.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset) / 2) + 1)) AS sample_statement
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
        GROUP BY qs.query_hash
        HAVING COUNT(*) > 1
           AND MAX(qs.max_worker_time) > 2 * NULLIF(MIN(NULLIF(qs.min_worker_time, 0)), 0)
        ORDER BY cpu_variance_ratio DESC
    """,

    "En Çok Logical Read Yapan Sorgular": """
        SELECT TOP 25
            qs.execution_count,
            qs.total_logical_reads,
            qs.total_logical_reads / qs.execution_count AS avg_logical_reads,
            qs.total_worker_time / 1000.0 AS total_cpu_ms,
            qs.total_elapsed_time / 1000.0 AS total_elapsed_ms,
            qs.last_execution_time,
            SUBSTRING(st.text, (qs.statement_start_offset / 2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(st.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset) / 2) + 1) AS statement_text
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
        ORDER BY qs.total_logical_reads DESC
    """,

    "En Çok Physical Read Yapan Sorgular": """
        SELECT TOP 25
            qs.execution_count,
            qs.total_physical_reads,
            qs.total_physical_reads / qs.execution_count AS avg_physical_reads,
            qs.total_logical_reads,
            qs.total_elapsed_time / 1000.0 AS total_elapsed_ms,
            qs.last_execution_time,
            SUBSTRING(st.text, (qs.statement_start_offset / 2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(st.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset) / 2) + 1) AS statement_text
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
        WHERE qs.total_physical_reads > 0
        ORDER BY qs.total_physical_reads DESC
    """,

    "CXPACKET / CXCONSUMER Wait Özeti": """
        SELECT
            wait_type,
            waiting_tasks_count,
            wait_time_ms,
            wait_time_ms / 1000.0 AS wait_time_sec,
            signal_wait_time_ms,
            max_wait_time_ms,
            CAST(100.0 * wait_time_ms / NULLIF(SUM(wait_time_ms) OVER (), 0) AS DECIMAL(5, 2)) AS pct_of_selected
        FROM sys.dm_os_wait_stats
        WHERE wait_type IN ('CXPACKET', 'CXCONSUMER', 'THREADPOOL', 'SOS_SCHEDULER_YIELD', 'PAGEIOLATCH_SH', 'PAGEIOLATCH_EX', 'WRITELOG', 'LCK_M_X', 'LCK_M_S', 'RESOURCE_SEMAPHORE')
        ORDER BY wait_time_ms DESC
    """,

    "Latch Contention Top": """
        SELECT TOP 30
            latch_class,
            waiting_requests_count,
            wait_time_ms,
            max_wait_time_ms,
            CAST(wait_time_ms * 1.0 / NULLIF(waiting_requests_count, 0) AS DECIMAL(12, 2)) AS avg_wait_ms
        FROM sys.dm_os_latch_stats
        WHERE waiting_requests_count > 0
        ORDER BY wait_time_ms DESC
    """,

    "=== INDEX VE SCHEMA SAĞLIĞI ===": "",

    "Yinelenen / Çakışan Indexler": """
        WITH index_cols AS (
            SELECT
                s.name AS schema_name,
                t.name AS table_name,
                i.name AS index_name,
                i.index_id,
                i.type_desc,
                i.is_unique,
                i.has_filter,
                STUFF((
                    SELECT ',' + c.name
                    FROM sys.index_columns ic2
                    INNER JOIN sys.columns c ON ic2.object_id = c.object_id AND ic2.column_id = c.column_id
                    WHERE ic2.object_id = i.object_id
                      AND ic2.index_id = i.index_id
                      AND ic2.is_included_column = 0
                    ORDER BY ic2.key_ordinal
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 1, '') AS key_columns
            FROM sys.indexes i
            INNER JOIN sys.tables t ON i.object_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE i.type > 0
              AND t.is_ms_shipped = 0
        )
        SELECT
            a.schema_name,
            a.table_name,
            a.index_name AS index_a,
            b.index_name AS index_b,
            a.key_columns,
            a.type_desc AS type_a,
            b.type_desc AS type_b
        FROM index_cols a
        INNER JOIN index_cols b
            ON a.schema_name = b.schema_name
           AND a.table_name = b.table_name
           AND a.key_columns = b.key_columns
           AND a.index_id < b.index_id
        ORDER BY a.schema_name, a.table_name, a.key_columns
    """,

    "Primary Key Olmayan Tablolar": """
        SELECT
            s.name AS schema_name,
            t.name AS table_name,
            t.create_date,
            t.modify_date
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE t.is_ms_shipped = 0
          AND NOT EXISTS (
              SELECT 1
              FROM sys.indexes i
              WHERE i.object_id = t.object_id
                AND i.is_primary_key = 1
          )
        ORDER BY s.name, t.name
    """,

    "Foreign Key Index Eksikleri": """
        SELECT
            fk_schema.name AS fk_schema,
            tp.name AS parent_table,
            fk.name AS foreign_key_name,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_column,
            ref_schema.name AS referenced_schema,
            tr.name AS referenced_table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
        INNER JOIN sys.schemas fk_schema ON tp.schema_id = fk_schema.schema_id
        INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
        INNER JOIN sys.schemas ref_schema ON tr.schema_id = ref_schema.schema_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM sys.index_columns ic
            INNER JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            WHERE ic.object_id = fkc.parent_object_id
              AND ic.column_id = fkc.parent_column_id
              AND ic.key_ordinal = 1
        )
        ORDER BY fk_schema.name, tp.name, fk.name
    """,

    "Heap Tablolar ve Forwarded Record": """
        SELECT
            OBJECT_SCHEMA_NAME(ps.object_id) AS schema_name,
            OBJECT_NAME(ps.object_id) AS table_name,
            ps.partition_number,
            ps.row_count,
            ps.forwarded_record_count,
            ps.page_count,
            CASE
                WHEN ps.forwarded_record_count > 0 THEN 'Forwarded record var - cluster index düşünün'
                ELSE 'Heap'
            END AS recommendation
        FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') ps
        INNER JOIN sys.indexes i ON ps.object_id = i.object_id AND ps.index_id = i.index_id
        WHERE i.type = 0
          AND OBJECTPROPERTY(ps.object_id, 'IsMsShipped') = 0
        ORDER BY ps.forwarded_record_count DESC, ps.row_count DESC
    """,

    "Identity Kapasiteye Yaklaşan Kolonlar": """
        SELECT
            OBJECT_SCHEMA_NAME(o.object_id) AS schema_name,
            o.name AS table_name,
            c.name AS column_name,
            t.name AS data_type,
            IDENT_CURRENT(OBJECT_SCHEMA_NAME(o.object_id) + '.' + o.name) AS current_identity,
            CASE t.name
                WHEN 'tinyint' THEN 255
                WHEN 'smallint' THEN 32767
                WHEN 'int' THEN 2147483647
                WHEN 'bigint' THEN 9223372036854775807
            END AS type_max,
            CAST(
                100.0 * IDENT_CURRENT(OBJECT_SCHEMA_NAME(o.object_id) + '.' + o.name)
                / NULLIF(CASE t.name
                    WHEN 'tinyint' THEN 255
                    WHEN 'smallint' THEN 32767
                    WHEN 'int' THEN 2147483647.0
                    WHEN 'bigint' THEN 9223372036854775807.0
                END, 0) AS DECIMAL(8, 4)
            ) AS pct_used
        FROM sys.identity_columns ic
        INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        INNER JOIN sys.objects o ON ic.object_id = o.object_id
        INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
        WHERE o.type = 'U'
          AND t.name IN ('tinyint', 'smallint', 'int', 'bigint')
        ORDER BY pct_used DESC
    """,

    "Partition ve Filegroup Dağılımı": """
        SELECT
            OBJECT_SCHEMA_NAME(p.object_id) AS schema_name,
            OBJECT_NAME(p.object_id) AS table_name,
            i.name AS index_name,
            p.partition_number,
            fg.name AS filegroup_name,
            p.rows,
            au.total_pages,
            CAST(au.total_pages * 8.0 / 1024 AS DECIMAL(12, 2)) AS total_mb
        FROM sys.partitions p
        INNER JOIN sys.indexes i ON p.object_id = i.object_id AND p.index_id = i.index_id
        INNER JOIN sys.allocation_units au ON p.partition_id = au.container_id
        LEFT JOIN sys.destination_data_spaces dds ON i.data_space_id = dds.partition_scheme_id AND p.partition_number = dds.destination_id
        LEFT JOIN sys.filegroups fg ON COALESCE(dds.data_space_id, i.data_space_id) = fg.data_space_id
        WHERE OBJECTPROPERTY(p.object_id, 'IsMsShipped') = 0
          AND au.type_desc = 'IN_ROW_DATA'
        ORDER BY total_mb DESC
    """,

    "=== YEDEKLEME VE RPO KONTROLÜ ===": "",

    "RPO Riski - Backup Gecikmeleri": """
        SELECT
            d.name AS database_name,
            d.recovery_model_desc,
            d.state_desc,
            MAX(CASE WHEN b.type = 'D' THEN b.backup_finish_date END) AS last_full_backup,
            MAX(CASE WHEN b.type = 'I' THEN b.backup_finish_date END) AS last_diff_backup,
            MAX(CASE WHEN b.type = 'L' THEN b.backup_finish_date END) AS last_log_backup,
            DATEDIFF(HOUR, MAX(CASE WHEN b.type = 'D' THEN b.backup_finish_date END), GETDATE()) AS hours_since_full,
            DATEDIFF(MINUTE, MAX(CASE WHEN b.type = 'L' THEN b.backup_finish_date END), GETDATE()) AS minutes_since_log,
            CASE
                WHEN MAX(CASE WHEN b.type = 'D' THEN b.backup_finish_date END) IS NULL THEN 'Full backup yok'
                WHEN d.recovery_model_desc = 'FULL'
                     AND MAX(CASE WHEN b.type = 'L' THEN b.backup_finish_date END) IS NULL THEN 'Log backup yok'
                WHEN d.recovery_model_desc = 'FULL'
                     AND DATEDIFF(HOUR, MAX(CASE WHEN b.type = 'L' THEN b.backup_finish_date END), GETDATE()) > 6 THEN 'Log backup gecikmeli'
                WHEN DATEDIFF(HOUR, MAX(CASE WHEN b.type = 'D' THEN b.backup_finish_date END), GETDATE()) > 24 THEN 'Full backup gecikmeli'
                ELSE 'Uygun'
            END AS rpo_status
        FROM sys.databases d
        LEFT JOIN msdb.dbo.backupset b ON d.name = b.database_name
        WHERE d.name NOT IN ('tempdb')
        GROUP BY d.name, d.recovery_model_desc, d.state_desc
        ORDER BY
            CASE
                WHEN MAX(CASE WHEN b.type = 'D' THEN b.backup_finish_date END) IS NULL THEN 0
                ELSE 1
            END,
            hours_since_full DESC
    """,

    "Suspect Pages (Bozuk Sayfa)": """
        SELECT
            DB_NAME(database_id) AS database_name,
            file_id,
            page_id,
            event_type,
            CASE event_type
                WHEN 1 THEN '823 veya 824 hata (kötü checksum)'
                WHEN 2 THEN 'Bad checksum'
                WHEN 3 THEN 'Torn page'
                WHEN 4 THEN 'Restored'
                WHEN 5 THEN 'Repaired'
                WHEN 7 THEN 'Deallocated'
                ELSE CAST(event_type AS VARCHAR(10))
            END AS event_description,
            error_count,
            last_update_date
        FROM msdb.dbo.suspect_pages
        ORDER BY last_update_date DESC
    """,

    "Autogrowth Olayları (Default Trace)": """
        SELECT TOP 100
            te.name AS event_name,
            t.DatabaseName,
            t.FileName,
            t.StartTime,
            t.IntegerData * 8 / 1024.0 AS growth_mb,
            t.ApplicationName,
            t.LoginName,
            t.HostName,
            t.Duration / 1000.0 AS duration_ms
        FROM sys.fn_trace_gettable(
            CONVERT(VARCHAR(150), (
                SELECT TOP 1 value
                FROM sys.fn_trace_getinfo(NULL)
                WHERE traceid = 1 AND property = 2
            )),
            DEFAULT
        ) t
        INNER JOIN sys.trace_events te ON t.EventClass = te.trace_event_id
        WHERE te.name IN ('Data File Auto Grow', 'Log File Auto Grow')
        ORDER BY t.StartTime DESC
    """,

    "=== GÜVENLİK VE ERİŞİM KONTROLÜ ===": "",

    "Sysadmin ve Yüksek Yetkili Loginler": """
        SELECT
            p.name AS principal_name,
            p.type_desc,
            p.is_disabled,
            p.create_date,
            p.modify_date,
            r.name AS server_role
        FROM sys.server_role_members rm
        INNER JOIN sys.server_principals r ON rm.role_principal_id = r.principal_id
        INNER JOIN sys.server_principals p ON rm.member_principal_id = p.principal_id
        WHERE r.name IN ('sysadmin', 'securityadmin', 'serveradmin', 'setupadmin', 'processadmin', 'diskadmin', 'dbcreator', 'bulkadmin')
        ORDER BY r.name, p.name
    """,

    "Zayıf Login Politikaları": """
        SELECT
            name AS login_name,
            type_desc,
            is_disabled,
            is_policy_checked,
            is_expiration_checked,
            create_date,
            modify_date,
            CASE
                WHEN is_policy_checked = 0 THEN 'Parola politikası kapalı'
                WHEN is_expiration_checked = 0 THEN 'Parola süresi dolma kapalı'
                ELSE 'Politika açık'
            END AS risk_note
        FROM sys.sql_logins
        WHERE is_policy_checked = 0
           OR is_expiration_checked = 0
        ORDER BY is_policy_checked, is_expiration_checked, name
    """,

    "Orphaned Database Users": """
        SELECT
            DB_NAME() AS database_name,
            dp.name AS database_user,
            dp.type_desc,
            dp.authentication_type_desc,
            dp.sid,
            dp.create_date
        FROM sys.database_principals dp
        LEFT JOIN sys.server_principals sp ON dp.sid = sp.sid
        WHERE dp.type IN ('S', 'U', 'G')
          AND dp.sid IS NOT NULL
          AND dp.sid <> 0x0
          AND sp.sid IS NULL
          AND dp.name NOT IN ('dbo', 'guest', 'INFORMATION_SCHEMA', 'sys')
        ORDER BY dp.name
    """,

    "Sertifika ve Key Son Kullanım Tarihleri": """
        SELECT
            name AS certificate_name,
            certificate_id,
            principal_id,
            pvt_key_encryption_type_desc,
            issuer_name,
            subject,
            start_date,
            expiry_date,
            DATEDIFF(DAY, GETDATE(), expiry_date) AS days_until_expiry,
            CASE
                WHEN expiry_date < GETDATE() THEN 'Süresi dolmuş'
                WHEN DATEDIFF(DAY, GETDATE(), expiry_date) <= 30 THEN '30 gün içinde dolacak'
                WHEN DATEDIFF(DAY, GETDATE(), expiry_date) <= 90 THEN '90 gün içinde dolacak'
                ELSE 'Geçerli'
            END AS status
        FROM sys.certificates
        ORDER BY expiry_date
    """,

    "Linked Server Envanteri": """
        SELECT
            s.name AS linked_server,
            s.product,
            s.provider,
            s.data_source,
            s.location,
            s.provider_string,
            s.catalog,
            s.modify_date,
            s.is_linked,
            s.is_remote_login_enabled,
            s.is_rpc_out_enabled,
            s.is_data_access_enabled,
            s.is_collation_compatible,
            s.uses_remote_collation
        FROM sys.servers s
        WHERE s.is_linked = 1
        ORDER BY s.name
    """,

    "Başarısız Login Ring Buffer": """
        SELECT TOP 100
            DATEADD(ms, -1 * (osi.cpu_ticks / (osi.cpu_ticks / osi.ms_ticks) - rb.timestamp), GETDATE()) AS event_time,
            CAST(rb.record AS XML).value('(//Error/ErrorCode)[1]', 'int') AS error_code,
            CAST(rb.record AS XML).value('(//Error/Severity)[1]', 'int') AS severity,
            CAST(rb.record AS XML).value('(//Error/State)[1]', 'int') AS state,
            CAST(rb.record AS XML).value('(//ErrorText)[1]', 'nvarchar(max)') AS error_text
        FROM sys.dm_os_ring_buffers rb
        CROSS JOIN sys.dm_os_sys_info osi
        WHERE rb.ring_buffer_type = 'RING_BUFFER_EXCEPTION'
        ORDER BY rb.timestamp DESC
    """,

    "=== SQL AGENT OPERASYON ===": "",

    "Job Başarı Oranı (Son 7 Gün)": """
        SELECT
            j.name AS job_name,
            j.enabled,
            COUNT(*) AS run_count,
            SUM(CASE WHEN h.run_status = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN h.run_status = 0 THEN 1 ELSE 0 END) AS failed_count,
            SUM(CASE WHEN h.run_status = 3 THEN 1 ELSE 0 END) AS canceled_count,
            CAST(100.0 * SUM(CASE WHEN h.run_status = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 2)) AS success_pct,
            MAX(CONVERT(DATETIME, CONVERT(CHAR(8), h.run_date)) + 
                STUFF(STUFF(RIGHT('000000' + CAST(h.run_time AS VARCHAR(6)), 6), 5, 0, ':'), 3, 0, ':')) AS last_run
        FROM msdb.dbo.sysjobs j
        INNER JOIN msdb.dbo.sysjobhistory h ON j.job_id = h.job_id
        WHERE h.step_id = 0
          AND CONVERT(DATETIME, CONVERT(CHAR(8), h.run_date)) >= DATEADD(DAY, -7, GETDATE())
        GROUP BY j.name, j.enabled
        ORDER BY success_pct ASC, failed_count DESC
    """,

    "Uzun Süredir Çalışmayan Job'lar": """
        SELECT
            j.name AS job_name,
            j.enabled,
            j.date_created,
            j.date_modified,
            MAX(CONVERT(DATETIME, CONVERT(CHAR(8), h.run_date)) +
                STUFF(STUFF(RIGHT('000000' + CAST(h.run_time AS VARCHAR(6)), 6), 5, 0, ':'), 3, 0, ':')) AS last_run,
            DATEDIFF(DAY,
                MAX(CONVERT(DATETIME, CONVERT(CHAR(8), h.run_date)) +
                    STUFF(STUFF(RIGHT('000000' + CAST(h.run_time AS VARCHAR(6)), 6), 5, 0, ':'), 3, 0, ':')),
                GETDATE()) AS days_since_last_run
        FROM msdb.dbo.sysjobs j
        LEFT JOIN msdb.dbo.sysjobhistory h ON j.job_id = h.job_id AND h.step_id = 0
        WHERE j.enabled = 1
        GROUP BY j.name, j.enabled, j.date_created, j.date_modified
        HAVING MAX(h.run_date) IS NULL
            OR DATEDIFF(DAY,
                MAX(CONVERT(DATETIME, CONVERT(CHAR(8), h.run_date)) +
                    STUFF(STUFF(RIGHT('000000' + CAST(h.run_time AS VARCHAR(6)), 6), 5, 0, ':'), 3, 0, ':')),
                GETDATE()) >= 7
        ORDER BY days_since_last_run DESC
    """,

    "=== ALWAYS ON DERİN İZLEME ===": "",

    "AG Senkronizasyon Gecikmesi": """
        SELECT
            ag.name AS ag_name,
            ar.replica_server_name,
            ars.role_desc,
            ars.operational_state_desc,
            ars.connected_state_desc,
            ars.synchronization_health_desc,
            drs.database_id,
            DB_NAME(drs.database_id) AS database_name,
            drs.synchronization_state_desc,
            drs.synchronization_health_desc,
            drs.log_send_queue_size,
            drs.log_send_rate,
            drs.redo_queue_size,
            drs.redo_rate,
            drs.last_commit_time,
            drs.last_hardened_time,
            drs.last_redone_time,
            CASE
                WHEN drs.redo_queue_size > 102400 THEN 'Yüksek redo kuyruğu'
                WHEN drs.log_send_queue_size > 102400 THEN 'Yüksek log send kuyruğu'
                ELSE 'Normal'
            END AS lag_hint
        FROM sys.dm_hadr_database_replica_states drs
        INNER JOIN sys.availability_replicas ar ON drs.replica_id = ar.replica_id
        INNER JOIN sys.dm_hadr_availability_replica_states ars ON ar.replica_id = ars.replica_id
        INNER JOIN sys.availability_groups ag ON ar.group_id = ag.group_id
        ORDER BY drs.redo_queue_size DESC, drs.log_send_queue_size DESC
    """,

    "AG Listener ve Endpoint Durumu": """
        SELECT
            ag.name AS ag_name,
            agl.dns_name AS listener_dns,
            agl.port,
            agl.is_conformant,
            agl.ip_configuration_string_from_cluster,
            te.name AS endpoint_name,
            te.state_desc AS endpoint_state,
            te.type_desc AS endpoint_type,
            te.protocol_desc
        FROM sys.availability_groups ag
        LEFT JOIN sys.availability_group_listeners agl ON ag.group_id = agl.group_id
        LEFT JOIN sys.database_mirroring_endpoints dme ON 1 = 1
        LEFT JOIN sys.tcp_endpoints te ON dme.endpoint_id = te.endpoint_id
        ORDER BY ag.name
    """,

    "=== TEMPDB VE TRANSACTION KONTROLÜ ===": "",

    "TempDB Dosya Dengesizliği": """
        SELECT
            mf.name AS logical_name,
            mf.physical_name,
            mf.size * 8 / 1024 AS size_mb,
            mf.max_size,
            mf.growth,
            mf.is_percent_growth,
            vfs.num_of_reads,
            vfs.num_of_writes,
            vfs.io_stall_read_ms,
            vfs.io_stall_write_ms,
            CAST(vfs.num_of_reads * 1.0 / NULLIF(SUM(vfs.num_of_reads) OVER (), 0) AS DECIMAL(5, 2)) AS read_share,
            CAST(vfs.num_of_writes * 1.0 / NULLIF(SUM(vfs.num_of_writes) OVER (), 0) AS DECIMAL(5, 2)) AS write_share
        FROM sys.master_files mf
        INNER JOIN sys.dm_io_virtual_file_stats(2, NULL) vfs ON mf.file_id = vfs.file_id
        WHERE mf.database_id = 2
          AND mf.type_desc = 'ROWS'
        ORDER BY mf.file_id
    """,

    "Açık Transaction ve Log Kullanımı": """
        SELECT
            at.transaction_id,
            at.name AS transaction_name,
            at.transaction_begin_time,
            DATEDIFF(SECOND, at.transaction_begin_time, GETDATE()) AS duration_seconds,
            at.transaction_type,
            at.transaction_state,
            st.session_id,
            s.login_name,
            s.host_name,
            s.program_name,
            DB_NAME(dt.database_id) AS database_name,
            dt.database_transaction_log_bytes_used,
            dt.database_transaction_log_bytes_reserved,
            dt.database_transaction_log_record_count
        FROM sys.dm_tran_active_transactions at
        INNER JOIN sys.dm_tran_session_transactions st ON at.transaction_id = st.transaction_id
        INNER JOIN sys.dm_exec_sessions s ON st.session_id = s.session_id
        LEFT JOIN sys.dm_tran_database_transactions dt ON at.transaction_id = dt.transaction_id
        WHERE s.is_user_process = 1
        ORDER BY at.transaction_begin_time
    """,

    "Aktif Lock ve Wait Detayı": """
        SELECT TOP 100
            tl.request_session_id AS session_id,
            s.login_name,
            s.host_name,
            s.program_name,
            DB_NAME(tl.resource_database_id) AS database_name,
            tl.resource_type,
            tl.resource_description,
            tl.request_mode,
            tl.request_status,
            wt.wait_type,
            wt.wait_duration_ms,
            wt.blocking_session_id,
            OBJECT_NAME(p.object_id, tl.resource_database_id) AS object_name
        FROM sys.dm_tran_locks tl
        LEFT JOIN sys.dm_os_waiting_tasks wt ON tl.lock_owner_address = wt.resource_address
        LEFT JOIN sys.partitions p ON tl.resource_associated_entity_id = p.hobt_id
        LEFT JOIN sys.dm_exec_sessions s ON tl.request_session_id = s.session_id
        WHERE tl.request_status <> 'GRANT'
           OR wt.blocking_session_id IS NOT NULL
        ORDER BY wt.wait_duration_ms DESC
    """,

    "=== YAPILANDIRMA VE KAPASİTE ===": "",

    "Varsayılan Olmayan Sunucu Ayarları": """
        SELECT
            name,
            value,
            value_in_use,
            minimum,
            maximum,
            description,
            is_dynamic,
            is_advanced
        FROM sys.configurations
        WHERE value <> value_in_use
           OR name IN (
                'max degree of parallelism',
                'cost threshold for parallelism',
                'max server memory (MB)',
                'min server memory (MB)',
                'optimize for ad hoc workloads',
                'backup compression default',
                'remote admin connections',
                'clr enabled',
                'xp_cmdshell',
                'Agent XPs',
                'Database Mail XPs',
                'Ole Automation Procedures'
           )
        ORDER BY name
    """,

    "Veritabanı Scoped Configuration": """
        SELECT
            name,
            value,
            value_for_secondary,
            is_value_default
        FROM sys.database_scoped_configurations
        ORDER BY name
    """,

    "Dosya Alanı ve Büyüme Riski": """
        SELECT
            DB_NAME(mf.database_id) AS database_name,
            mf.name AS logical_name,
            mf.type_desc,
            mf.physical_name,
            CAST(mf.size * 8.0 / 1024 AS DECIMAL(12, 2)) AS size_mb,
            CASE
                WHEN mf.max_size = -1 THEN NULL
                ELSE CAST(mf.max_size * 8.0 / 1024 AS DECIMAL(12, 2))
            END AS max_size_mb,
            CASE
                WHEN mf.is_percent_growth = 1 THEN CAST(mf.growth AS VARCHAR(20)) + ' %'
                ELSE CAST(mf.growth * 8 / 1024 AS VARCHAR(20)) + ' MB'
            END AS growth_setting,
            mf.is_percent_growth,
            CASE
                WHEN mf.max_size > 0 AND mf.size >= mf.max_size * 0.9 THEN 'Max size sınırına yakın'
                WHEN mf.is_percent_growth = 1 AND mf.growth >= 25 THEN 'Yüzdesel büyüme agresif'
                WHEN mf.is_percent_growth = 0 AND mf.growth * 8 / 1024 < 64 AND mf.type_desc = 'ROWS' THEN 'Küçük büyüme adımı'
                ELSE 'Kontrol altında'
            END AS capacity_hint
        FROM sys.master_files mf
        ORDER BY database_name, mf.type_desc, mf.file_id
    """,

    "Query Store Durum Özeti": """
        SELECT
            DB_NAME() AS database_name,
            actual_state_desc,
            readonly_reason,
            current_storage_size_mb,
            max_storage_size_mb,
            CAST(100.0 * current_storage_size_mb / NULLIF(max_storage_size_mb, 0) AS DECIMAL(5, 2)) AS storage_used_pct,
            interval_length_minutes,
            stale_query_threshold_days,
            max_plans_per_query,
            query_capture_mode_desc,
            size_based_cleanup_mode_desc,
            flush_interval_seconds
        FROM sys.database_query_store_options
    """,

    "CDC / Change Tracking Durumu": """
        SELECT
            DB_NAME() AS database_name,
            'Change Tracking' AS feature_name,
            CASE WHEN EXISTS (SELECT 1 FROM sys.change_tracking_databases WHERE database_id = DB_ID())
                THEN 'Açık' ELSE 'Kapalı' END AS status,
            (SELECT is_auto_cleanup_on FROM sys.change_tracking_databases WHERE database_id = DB_ID()) AS auto_cleanup,
            (SELECT retention_period FROM sys.change_tracking_databases WHERE database_id = DB_ID()) AS retention_period,
            (SELECT retention_period_units_desc FROM sys.change_tracking_databases WHERE database_id = DB_ID()) AS retention_units
        UNION ALL
        SELECT
            DB_NAME(),
            'CDC',
            CASE WHEN is_cdc_enabled = 1 THEN 'Açık' ELSE 'Kapalı' END,
            NULL,
            NULL,
            NULL
        FROM sys.databases
        WHERE database_id = DB_ID()
    """,

    "Service Broker Kuyruk Derinliği": """
        SELECT
            SCHEMA_NAME(q.schema_id) AS schema_name,
            q.name AS queue_name,
            q.is_activation_enabled,
            q.is_receive_enabled,
            q.is_enqueue_enabled,
            q.activation_max_queue_readers,
            p.rows AS approximate_rows
        FROM sys.service_queues q
        LEFT JOIN sys.internal_tables it ON q.object_id = it.parent_object_id AND it.internal_type_desc = 'QUEUE_MESSAGES'
        LEFT JOIN sys.partitions p ON it.object_id = p.object_id AND p.index_id IN (0, 1)
        WHERE q.is_ms_shipped = 0
        ORDER BY p.rows DESC, q.name
    """,

    "In-Memory OLTP Kullanımı": """
        SELECT
            OBJECT_SCHEMA_NAME(object_id) AS schema_name,
            OBJECT_NAME(object_id) AS table_name,
            memory_allocated_for_table_kb,
            memory_used_by_table_kb,
            memory_allocated_for_indexes_kb,
            memory_used_by_indexes_kb
        FROM sys.dm_db_xtp_table_memory_stats
        WHERE object_id > 0
        ORDER BY memory_used_by_table_kb DESC
    """,

    "Temporal Tablo Envanteri": """
        SELECT
            SCHEMA_NAME(t.schema_id) AS schema_name,
            t.name AS temporal_table,
            SCHEMA_NAME(h.schema_id) AS history_schema,
            h.name AS history_table,
            t.temporal_type_desc,
            t.create_date,
            t.modify_date
        FROM sys.tables t
        LEFT JOIN sys.tables h ON t.history_table_id = h.object_id
        WHERE t.temporal_type <> 0
        ORDER BY schema_name, temporal_table
    """,

    "=== BAĞLANTI VE OTURUM ANALİZİ ===": "",

    "Uygulama Bazlı Bağlantı Dağılımı": """
        SELECT
            COALESCE(program_name, '(boş)') AS program_name,
            COALESCE(host_name, '(boş)') AS host_name,
            COALESCE(login_name, '(boş)') AS login_name,
            COUNT(*) AS session_count,
            SUM(CASE WHEN status = 'sleeping' THEN 1 ELSE 0 END) AS sleeping_count,
            SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running_count,
            SUM(cpu_time) AS total_cpu_time,
            SUM(memory_usage) AS total_memory_usage,
            SUM(reads) AS total_reads,
            SUM(writes) AS total_writes
        FROM sys.dm_exec_sessions
        WHERE is_user_process = 1
        GROUP BY program_name, host_name, login_name
        ORDER BY session_count DESC
    """,

    "Idle Session ve Sleeping Connections": """
        SELECT
            session_id,
            login_name,
            host_name,
            program_name,
            status,
            login_time,
            last_request_start_time,
            last_request_end_time,
            DATEDIFF(MINUTE, last_request_end_time, GETDATE()) AS idle_minutes,
            cpu_time,
            memory_usage,
            reads,
            writes,
            open_transaction_count
        FROM sys.dm_exec_sessions
        WHERE is_user_process = 1
          AND status = 'sleeping'
          AND open_transaction_count = 0
          AND DATEDIFF(MINUTE, last_request_end_time, GETDATE()) >= 30
        ORDER BY idle_minutes DESC
    """,

    "Açık Transaction ile Sleeping Session": """
        SELECT
            s.session_id,
            s.login_name,
            s.host_name,
            s.program_name,
            s.status,
            s.open_transaction_count,
            s.last_request_start_time,
            s.last_request_end_time,
            DATEDIFF(MINUTE, s.last_request_end_time, GETDATE()) AS idle_with_tran_minutes,
            DB_NAME(s.database_id) AS database_name
        FROM sys.dm_exec_sessions s
        WHERE s.is_user_process = 1
          AND s.open_transaction_count > 0
          AND s.status = 'sleeping'
        ORDER BY idle_with_tran_minutes DESC
    """,

    "=== HATA VE RING BUFFER ===": "",

    "Ring Buffer Exception Özeti": """
        SELECT TOP 100
            DATEADD(ms, -1 * (osi.cpu_ticks / (osi.cpu_ticks / osi.ms_ticks) - rb.timestamp), GETDATE()) AS event_time,
            CAST(rb.record AS XML).value('(//Error/ErrorCode)[1]', 'int') AS error_code,
            CAST(rb.record AS XML).value('(//Error/Severity)[1]', 'int') AS severity,
            CAST(rb.record AS XML).value('(//Error/State)[1]', 'int') AS state,
            LEFT(CAST(rb.record AS XML).value('(//ErrorText)[1]', 'nvarchar(max)'), 400) AS error_text
        FROM sys.dm_os_ring_buffers rb
        CROSS JOIN sys.dm_os_sys_info osi
        WHERE rb.ring_buffer_type = 'RING_BUFFER_EXCEPTION'
        ORDER BY rb.timestamp DESC
    """,

    "Ring Buffer Connectivity Hataları": """
        SELECT TOP 100
            DATEADD(ms, -1 * (osi.cpu_ticks / (osi.cpu_ticks / osi.ms_ticks) - rb.timestamp), GETDATE()) AS event_time,
            CAST(rb.record AS XML) AS record_xml
        FROM sys.dm_os_ring_buffers rb
        CROSS JOIN sys.dm_os_sys_info osi
        WHERE rb.ring_buffer_type = 'RING_BUFFER_CONNECTIVITY'
        ORDER BY rb.timestamp DESC
    """,

    "Ring Buffer Scheduler Monitor": """
        SELECT TOP 50
            DATEADD(ms, -1 * (osi.cpu_ticks / (osi.cpu_ticks / osi.ms_ticks) - rb.timestamp), GETDATE()) AS event_time,
            CAST(rb.record AS XML) AS record_xml
        FROM sys.dm_os_ring_buffers rb
        CROSS JOIN sys.dm_os_sys_info osi
        WHERE rb.ring_buffer_type = 'RING_BUFFER_SCHEDULER_MONITOR'
        ORDER BY rb.timestamp DESC
    """,
}


# Sorgu açıklamaları (UI bilgi paneli için)
QUERY_DESCRIPTIONS = {
    "Sunucu Anlık Durum Kartı": "Oturum, blokaj, bellek ve çevrimdışı veritabanı sayılarını tek bakışta gösterir.",
    "Page Life Expectancy ve Buffer Hit": "Bellek baskısı ve buffer cache sağlığını performans sayaçlarından okur.",
    "Scheduler ve Runnable Task Yoğunluğu": "CPU kuyruğu ve disk I/O bekleyen scheduler'ları listeler.",
    "Memory Grant Bekleyen Sorgular": "RESOURCE_SEMAPHORE ve bellek grant bekleyen istekleri analiz eder.",
    "Ad-hoc Plan Cache Şişmesi": "Tek kullanımlık planların cache'i şişirip şişirmediğini gösterir.",
    "Parameter Sniffing Adayları": "Aynı query_hash için yüksek CPU varyansı olan planları bulur.",
    "Yinelenen / Çakışan Indexler": "Aynı anahtar kolonlara sahip potansiyel yinelenen indexleri listeler.",
    "Foreign Key Index Eksikleri": "FK kolonlarında destekleyici index olmayan ilişkileri bulur.",
    "RPO Riski - Backup Gecikmeleri": "Full/diff/log backup gecikmelerine göre RPO riskini sınıflandırır.",
    "Sysadmin ve Yüksek Yetkili Loginler": "Sunucu seviyesi yüksek yetkili rolleri ve üyelerini listeler.",
    "Orphaned Database Users": "Sunucu login'i olmayan veritabanı kullanıcılarını bulur.",
    "AG Senkronizasyon Gecikmesi": "Availability Group redo/log send kuyruklarını izler.",
    "TempDB Dosya Dengesizliği": "TempDB data dosyaları arasında I/O dağılımını karşılaştırır.",
    "Açık Transaction ile Sleeping Session": "Transaction açık bırakılmış idle oturumları tespit eder.",
    "Ring Buffer Exception Özeti": "xp_readerrorlog yerine ring buffer üzerinden son exception'ları gösterir.",
    "Job Başarı Oranı (Son 7 Gün)": "SQL Agent job başarı/başarısızlık oranını özetler.",
    "Varsayılan Olmayan Sunucu Ayarları": "Kritik ve değiştirilmiş sp_configure ayarlarını listeler.",
    "Query Store Durum Özeti": "Query Store doluluk ve yakalama modunu gösterir.",
}
