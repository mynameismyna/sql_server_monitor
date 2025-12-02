"""
Hazır analiz sorguları modülü
"""
import json
import os

USER_QUERIES_FILE = "user_queries.json"

PREDEFINED_QUERIES = {
    "Aktif Bağlantılar": """
        SELECT 
            session_id,
            login_name,
            host_name,
            program_name,
            status,
            cpu_time,
            memory_usage,
            reads,
            writes,
            logical_reads,
            login_time,
            last_request_start_time
        FROM sys.dm_exec_sessions
        WHERE is_user_process = 1
        ORDER BY cpu_time DESC
    """,
    
    "Yavaş Çalışan Sorgular": """
        SELECT TOP 20
            qs.execution_count,
            qs.total_elapsed_time / 1000000.0 AS total_elapsed_time_seconds,
            qs.total_elapsed_time / qs.execution_count / 1000000.0 AS avg_elapsed_time_seconds,
            qs.total_worker_time / 1000000.0 AS total_cpu_seconds,
            qs.total_logical_reads,
            qs.total_logical_writes,
            SUBSTRING(qt.text, (qs.statement_start_offset/2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1) AS query_text,
            qt.text AS full_query_text,
            qs.last_execution_time
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        ORDER BY qs.total_elapsed_time DESC
    """,
    
    "SQL Server Hataları (Son 24 Saat)": """
        -- Not: Bu sorgu xp_readerrorlog stored procedure'ünü kullanır
        -- Sonuçları görmek için SQL Server Management Studio'da 
        -- EXEC xp_readerrorlog 0, 1 komutunu çalıştırabilirsiniz
        SELECT 
            'Error Log' AS log_source,
            GETDATE() AS current_time,
            'Son 24 saatteki hataları görmek için SQL Server Management Studio''da EXEC xp_readerrorlog 0, 1 komutunu çalıştırın' AS note
    """,
    
    "Veritabanı Boyutları": """
        SELECT 
            name AS database_name,
            CAST(SUM(size) * 8.0 / 1024 AS DECIMAL(10, 2)) AS size_mb,
            CAST(SUM(size) * 8.0 / 1024 / 1024 AS DECIMAL(10, 2)) AS size_gb
        FROM sys.master_files
        GROUP BY name
        ORDER BY size_mb DESC
    """,
    
    "Bekleyen İşlemler (Blocking)": """
        SELECT 
            blocking_session_id,
            session_id,
            wait_type,
            wait_time,
            wait_resource,
            transaction_id
        FROM sys.dm_exec_requests
        WHERE blocking_session_id <> 0
    """,
    
    "En Çok CPU Kullanan Sorgular": """
        SELECT TOP 20
            qs.execution_count,
            qs.total_worker_time / 1000000.0 AS total_cpu_seconds,
            qs.total_worker_time / qs.execution_count / 1000000.0 AS avg_cpu_seconds,
            SUBSTRING(qt.text, (qs.statement_start_offset/2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1) AS query_text
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        ORDER BY qs.total_worker_time DESC
    """,
    
    "Aktif İşlemler": """
        SELECT 
            session_id,
            status,
            command,
            blocking_session_id,
            wait_type,
            wait_time,
            cpu_time,
            total_elapsed_time / 1000.0 AS elapsed_time_seconds,
            reads,
            writes,
            logical_reads
        FROM sys.dm_exec_requests
        WHERE session_id > 50
        ORDER BY total_elapsed_time DESC
    """,
    
    "Veritabanı Dosya Bilgileri": """
        SELECT 
            DB_NAME(database_id) AS database_name,
            name AS logical_name,
            physical_name,
            CAST(size * 8.0 / 1024 AS DECIMAL(10, 2)) AS size_mb,
            type_desc
        FROM sys.master_files
        WHERE DB_NAME(database_id) = DB_NAME()
        ORDER BY size DESC
    """,
    
    "Tablo Satır Sayıları": """
        SELECT 
            t.name AS table_name,
            p.rows AS row_count,
            CAST(SUM(a.total_pages) * 8.0 / 1024 AS DECIMAL(10, 2)) AS total_space_mb
        FROM sys.tables t
        INNER JOIN sys.indexes i ON t.object_id = i.object_id
        INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
        WHERE t.is_ms_shipped = 0
        GROUP BY t.name, p.rows
        ORDER BY p.rows DESC
    """,
    
    "Bloke'ye Sebep Olan Sorgular": """
        SELECT
            x.session_id,
            x.host_name,
            x.login_name,
            DB_NAME(x.database_id) as DB_NAME,
            x.start_time,
            x.totalReads,
            x.totalWrites,
            x.totalCPU,
            x.writes_in_tempdb,
            (
                SELECT 
                    text AS [text()]
                FROM sys.dm_exec_sql_text(x.sql_handle)
                FOR XML PATH(''), TYPE
            ) AS sql_text,
            COALESCE(x.blocking_session_id, 0) AS blocking_session_id,
            (
                SELECT 
                    p.text
                FROM 
                (
                    SELECT 
                        MIN(sql_handle) AS sql_handle
                    FROM sys.dm_exec_requests r2
                    WHERE 
                        r2.session_id = x.blocking_session_id
                ) AS r_blocking
                CROSS APPLY
                (
                    SELECT 
                        text AS [text()]
                    FROM sys.dm_exec_sql_text(r_blocking.sql_handle)
                    FOR XML PATH(''), TYPE
                ) p (text)
            ) AS blocking_text
        FROM
        (
            SELECT
                r.session_id,
                s.host_name,
                s.login_name,
                r.start_time,
                r.sql_handle,
                r.database_id,
                r.blocking_session_id,
                SUM(r.reads) AS totalReads,
                SUM(r.writes) AS totalWrites,
                SUM(r.cpu_time) AS totalCPU,
                SUM(tsu.user_objects_alloc_page_count + tsu.internal_objects_alloc_page_count) AS writes_in_tempdb
            FROM sys.dm_exec_requests r
            JOIN sys.dm_exec_sessions s ON s.session_id = r.session_id
            JOIN sys.dm_db_task_space_usage tsu ON s.session_id = tsu.session_id and r.request_id = tsu.request_id
            WHERE 1=1
            and r.status IN ('running', 'runnable', 'suspended')
            GROUP BY
                r.session_id,
                s.host_name,
                s.login_name,
                r.start_time,
                r.sql_handle,
                r.database_id,
                r.blocking_session_id
        ) x
        WHERE 1=1
        ORDER BY blocking_session_id ASC, host_name ASC
    """,
    
    "Bellek Kullanımı": """
        SELECT 
            (committed_kb / 1024.0) AS memory_committed_mb,
            (committed_target_kb / 1024.0) AS memory_target_mb,
            ((committed_target_kb - committed_kb) / 1024.0) AS memory_available_mb,
            (committed_kb * 100.0 / NULLIF(committed_target_kb, 0)) AS memory_utilization_percent,
            physical_memory_kb / 1024.0 AS physical_memory_mb,
            virtual_memory_kb / 1024.0 AS virtual_memory_mb
        FROM sys.dm_os_sys_info
    """,
    
    "Disk I/O İstatistikleri": """
        SELECT 
            DB_NAME(database_id) AS database_name,
            file_id,
            io_stall_read_ms / NULLIF(num_of_reads, 0) AS avg_read_latency_ms,
            io_stall_write_ms / NULLIF(num_of_writes, 0) AS avg_write_latency_ms,
            num_of_reads,
            num_of_writes,
            (num_of_bytes_read / 1024.0 / 1024.0) AS read_mb,
            (num_of_bytes_written / 1024.0 / 1024.0) AS write_mb,
            io_stall_read_ms,
            io_stall_write_ms
        FROM sys.dm_io_virtual_file_stats(NULL, NULL)
        ORDER BY (io_stall_read_ms + io_stall_write_ms) DESC
    """,
    
    "Wait Statistics (Bekleme İstatistikleri)": """
        SELECT TOP 20
            wait_type,
            waiting_tasks_count,
            wait_time_ms,
            wait_time_ms / NULLIF(waiting_tasks_count, 0) AS avg_wait_time_ms,
            max_wait_time_ms,
            signal_wait_time_ms
        FROM sys.dm_os_wait_stats
        WHERE wait_type NOT IN (
            'CLR_SEMAPHORE', 'LAZYWRITER_SLEEP', 'RESOURCE_QUEUE',
            'SLEEP_TASK', 'SLEEP_SYSTEMTASK', 'SQLTRACE_BUFFER_FLUSH',
            'WAITFOR', 'LOGMGR_QUEUE', 'CHECKPOINT_QUEUE',
            'REQUEST_FOR_DEADLOCK_SEARCH', 'XE_TIMER_EVENT', 'BROKER_TO_FLUSH',
            'BROKER_TASK_STOP', 'CLR_MANUAL_EVENT', 'CLR_AUTO_EVENT',
            'DISPATCHER_QUEUE_SEMAPHORE', 'FT_IFTS_SCHEDULER_IDLE_WAIT',
            'XE_DISPATCHER_WAIT', 'XE_DISPATCHER_JOIN', 'SQLTRACE_INCREMENTAL_FLUSH_SLEEP'
        )
        ORDER BY wait_time_ms DESC
    """,
    
    "Index Kullanım İstatistikleri": """
        SELECT TOP 50
            OBJECT_NAME(s.object_id) AS table_name,
            i.name AS index_name,
            s.user_seeks,
            s.user_scans,
            s.user_lookups,
            s.user_updates,
            s.user_seeks + s.user_scans + s.user_lookups AS total_reads,
            CASE 
                WHEN s.user_seeks + s.user_scans + s.user_lookups = 0 THEN 0
                ELSE (s.user_updates * 100.0) / (s.user_seeks + s.user_scans + s.user_lookups)
            END AS update_to_read_ratio
        FROM sys.dm_db_index_usage_stats s
        INNER JOIN sys.indexes i ON s.object_id = i.object_id AND s.index_id = i.index_id
        WHERE s.database_id = DB_ID()
        AND OBJECTPROPERTY(s.object_id, 'IsUserTable') = 1
        ORDER BY (s.user_seeks + s.user_scans + s.user_lookups) DESC
    """,
    
    "Kullanılmayan Indexler": """
        SELECT 
            OBJECT_NAME(i.object_id) AS table_name,
            i.name AS index_name,
            i.type_desc,
            s.user_seeks,
            s.user_scans,
            s.user_lookups,
            s.user_updates,
            s.last_user_seek,
            s.last_user_scan,
            s.last_user_lookup
        FROM sys.indexes i
        LEFT JOIN sys.dm_db_index_usage_stats s 
            ON i.object_id = s.object_id 
            AND i.index_id = s.index_id 
            AND s.database_id = DB_ID()
        WHERE OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
        AND i.is_primary_key = 0
        AND i.is_unique_constraint = 0
        AND (s.user_seeks IS NULL OR s.user_seeks = 0)
        AND (s.user_scans IS NULL OR s.user_scans = 0)
        AND (s.user_lookups IS NULL OR s.user_lookups = 0)
        ORDER BY OBJECT_NAME(i.object_id), i.name
    """,
    
    "Eksik Indexler (Öneriler)": """
        SELECT TOP 50
            OBJECT_NAME(d.object_id) AS table_name,
            d.equality_columns,
            d.inequality_columns,
            d.included_columns,
            s.user_seeks,
            s.user_scans,
            s.avg_total_user_cost * (s.avg_user_impact / 100.0) * (s.user_seeks + s.user_scans) AS improvement_measure,
            s.last_user_seek,
            s.last_user_scan
        FROM sys.dm_db_missing_index_details d
        INNER JOIN sys.dm_db_missing_index_groups g ON d.index_handle = g.index_handle
        INNER JOIN sys.dm_db_missing_index_group_stats s ON g.index_group_handle = s.group_handle
        WHERE d.database_id = DB_ID()
        ORDER BY improvement_measure DESC
    """,
    
    "Deadlock Bilgileri (Son 24 Saat)": """
        SELECT TOP 20
            CONVERT(datetime, SWITCHOFFSET(CONVERT(datetimeoffset, event_time), DATENAME(TzOffset, SYSDATETIMEOFFSET()))) AS event_time,
            CAST(event_data AS XML).value('(/event/data[@name=''database_name'']/value)[1]', 'nvarchar(128)') AS database_name,
            CAST(event_data AS XML).value('(/event/data[@name=''deadlock_cycle_id'']/value)[1]', 'int') AS deadlock_cycle_id,
            CAST(event_data AS XML).value('(/event/data[@name=''victim_process'']/value)[1]', 'nvarchar(50)') AS victim_process
        FROM (
            SELECT 
                CONVERT(datetime, SWITCHOFFSET(CONVERT(datetimeoffset, event_time), DATENAME(TzOffset, SYSDATETIMEOFFSET()))) AS event_time,
                event_data
            FROM sys.fn_xe_file_target_read_file('system_health*.xel', NULL, NULL, NULL)
            WHERE object_name = 'xml_deadlock_report'
            AND CONVERT(datetime, SWITCHOFFSET(CONVERT(datetimeoffset, event_time), DATENAME(TzOffset, SYSDATETIMEOFFSET()))) >= DATEADD(HOUR, -24, GETDATE())
        ) AS deadlock_data
        ORDER BY event_time DESC
    """,
    
    "Transaction Log Durumu": """
        SELECT 
            name AS database_name,
            recovery_model_desc,
            log_reuse_wait_desc,
            CAST(SUM(size) * 8.0 / 1024 AS DECIMAL(10, 2)) AS log_size_mb,
            CAST(SUM(max_size) * 8.0 / 1024 AS DECIMAL(10, 2)) AS max_log_size_mb
        FROM sys.master_files mf
        INNER JOIN sys.databases d ON mf.database_id = d.database_id
        WHERE mf.type = 1  -- Log files
        GROUP BY name, recovery_model_desc, log_reuse_wait_desc
        ORDER BY log_size_mb DESC
    """,
    
    "Lock Bilgileri": """
        SELECT 
            DB_NAME(resource_database_id) AS database_name,
            resource_type,
            resource_subtype,
            resource_associated_entity_id,
            request_mode,
            request_type,
            request_status,
            request_session_id,
            request_owner_type,
            COUNT(*) AS lock_count
        FROM sys.dm_tran_locks
        WHERE resource_database_id = DB_ID()
        GROUP BY 
            resource_database_id,
            resource_type,
            resource_subtype,
            resource_associated_entity_id,
            request_mode,
            request_type,
            request_status,
            request_session_id,
            request_owner_type
        ORDER BY lock_count DESC
    """,
    
    "TempDB Kullanımı": """
        SELECT 
            session_id,
            request_id,
            (user_objects_alloc_page_count * 8.0 / 1024) AS user_objects_mb,
            (user_objects_dealloc_page_count * 8.0 / 1024) AS user_objects_dealloc_mb,
            (internal_objects_alloc_page_count * 8.0 / 1024) AS internal_objects_mb,
            (internal_objects_dealloc_page_count * 8.0 / 1024) AS internal_objects_dealloc_mb
        FROM sys.dm_db_task_space_usage
        WHERE session_id > 50
        ORDER BY (user_objects_alloc_page_count + internal_objects_alloc_page_count) DESC
    """,
    
    "SQL Server Versiyon ve Yapılandırma": """
        SELECT 
            @@VERSION AS sql_server_version,
            SERVERPROPERTY('ProductVersion') AS product_version,
            SERVERPROPERTY('ProductLevel') AS product_level,
            SERVERPROPERTY('Edition') AS edition,
            SERVERPROPERTY('MachineName') AS machine_name,
            SERVERPROPERTY('ServerName') AS server_name,
            SERVERPROPERTY('InstanceName') AS instance_name,
            SERVERPROPERTY('IsClustered') AS is_clustered,
            SERVERPROPERTY('ComputerNamePhysicalNetBIOS') AS physical_netbios,
            (SELECT value_in_use FROM sys.configurations WHERE name = 'max degree of parallelism') AS max_dop,
            (SELECT value_in_use FROM sys.configurations WHERE name = 'max server memory (MB)') AS max_server_memory_mb,
            (SELECT value_in_use FROM sys.configurations WHERE name = 'min server memory (MB)') AS min_server_memory_mb
    """,
    
    "Plan Cache İstatistikleri": """
        SELECT TOP 20
            objtype AS object_type,
            COUNT(*) AS cache_count,
            SUM(size_in_bytes) / 1024.0 / 1024.0 AS total_size_mb,
            AVG(size_in_bytes) / 1024.0 AS avg_size_kb,
            SUM(usecounts) AS total_use_counts,
            AVG(usecounts) AS avg_use_counts
        FROM sys.dm_exec_cached_plans
        GROUP BY objtype
        ORDER BY total_size_mb DESC
    """,
    
    "Veritabanı Backup Durumu": """
        SELECT 
            d.name AS database_name,
            d.recovery_model_desc,
            MAX(b.backup_finish_date) AS last_backup_date,
            DATEDIFF(HOUR, MAX(b.backup_finish_date), GETDATE()) AS hours_since_backup,
            CASE 
                WHEN MAX(b.backup_finish_date) IS NULL THEN 'Backup Yapılmamış'
                WHEN DATEDIFF(HOUR, MAX(b.backup_finish_date), GETDATE()) > 24 THEN 'Uyarı: 24 Saatten Eski'
                ELSE 'OK'
            END AS backup_status
        FROM sys.databases d
        LEFT JOIN msdb.dbo.backupset b ON d.name = b.database_name
        WHERE d.state_desc = 'ONLINE'
        GROUP BY d.name, d.recovery_model_desc
        ORDER BY hours_since_backup DESC
    """,
    
    "SQL Server Servis Durumu": """
        SELECT 
            servicename AS service_name,
            status_desc,
            startup_type_desc,
            service_account,
            is_clustered,
            cluster_nodename
        FROM sys.dm_server_services
        ORDER BY servicename
    """,
    
    "En Çok Bellek Kullanan Sorgular": """
        SELECT TOP 20
            qs.execution_count,
            (qs.total_logical_reads + qs.total_logical_writes) AS total_logical_io,
            qs.total_logical_reads,
            qs.total_logical_writes,
            qs.total_physical_reads,
            SUBSTRING(qt.text, (qs.statement_start_offset/2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1) AS query_text
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        ORDER BY (qs.total_logical_reads + qs.total_logical_writes) DESC
    """,
    
    "=== PERFORMANS ANALİZİ ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Performans Analizi Kategorisi' AS category
    """,
    
    "En Çok Çalıştırılan Sorgular": """
        SELECT TOP 50
            qs.execution_count,
            qs.total_elapsed_time / 1000000.0 AS total_elapsed_time_seconds,
            qs.total_elapsed_time / qs.execution_count / 1000000.0 AS avg_elapsed_time_seconds,
            qs.total_worker_time / 1000000.0 AS total_cpu_seconds,
            SUBSTRING(qt.text, (qs.statement_start_offset/2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1) AS query_text,
            qs.last_execution_time
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        ORDER BY qs.execution_count DESC
    """,
    
    "Paralel Çalışan Sorgular": """
        SELECT TOP 20
            qs.execution_count,
            qs.total_elapsed_time / 1000000.0 AS total_elapsed_time_seconds,
            qs.max_elapsed_time / 1000000.0 AS max_elapsed_time_seconds,
            qs.total_worker_time / 1000000.0 AS total_cpu_seconds,
            qs.total_physical_reads,
            qs.total_logical_reads,
            SUBSTRING(qt.text, (qs.statement_start_offset/2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1) AS query_text
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        WHERE qs.total_worker_time > qs.total_elapsed_time * 1000
        ORDER BY (qs.total_worker_time - qs.total_elapsed_time * 1000) DESC
    """,
    
    "Plan Cache Boyutu ve Kullanımı": """
        SELECT 
            objtype AS object_type,
            COUNT(*) AS cache_count,
            SUM(size_in_bytes) / 1024.0 / 1024.0 AS total_size_mb,
            AVG(size_in_bytes) / 1024.0 AS avg_size_kb,
            SUM(usecounts) AS total_use_counts,
            AVG(usecounts) AS avg_use_counts,
            SUM(CASE WHEN usecounts = 1 THEN 1 ELSE 0 END) AS single_use_plans,
            SUM(CASE WHEN usecounts = 1 THEN size_in_bytes ELSE 0 END) / 1024.0 / 1024.0 AS single_use_size_mb
        FROM sys.dm_exec_cached_plans
        GROUP BY objtype
        ORDER BY total_size_mb DESC
    """,
    
    "=== VERİTABANI SAĞLIK DURUMU ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Veritabanı Sağlık Durumu Kategorisi' AS category
    """,
    
    "Veritabanı Durumları": """
        SELECT 
            name AS database_name,
            state_desc AS state,
            recovery_model_desc AS recovery_model,
            compatibility_level,
            collation_name,
            user_access_desc AS user_access,
            is_read_only,
            is_auto_close_on,
            is_auto_shrink_on,
            create_date,
            DATEDIFF(DAY, create_date, GETDATE()) AS age_days
        FROM sys.databases
        ORDER BY name
    """,
    
    "Veritabanı Dosya Büyüme Durumu": """
        SELECT 
            DB_NAME(database_id) AS database_name,
            name AS logical_name,
            physical_name,
            type_desc,
            CAST(size * 8.0 / 1024 AS DECIMAL(10, 2)) AS current_size_mb,
            CAST(max_size * 8.0 / 1024 AS DECIMAL(10, 2)) AS max_size_mb,
            CASE 
                WHEN max_size = -1 THEN 'Sınırsız'
                WHEN max_size = 268435456 THEN 'Sınırsız'
                ELSE CAST((max_size - size) * 8.0 / 1024 AS DECIMAL(10, 2))
            END AS available_growth_mb,
            is_percent_growth,
            CASE 
                WHEN is_percent_growth = 1 THEN CAST(growth AS VARCHAR) + '%'
                ELSE CAST(growth * 8.0 / 1024 AS VARCHAR) + ' MB'
            END AS growth_setting
        FROM sys.master_files
        ORDER BY database_id, type_desc, file_id
    """,
    
    "Statistics Güncellik Durumu": """
        SELECT 
            OBJECT_SCHEMA_NAME(s.object_id) AS schema_name,
            OBJECT_NAME(s.object_id) AS table_name,
            s.name AS statistics_name,
            STATS_DATE(s.object_id, s.stats_id) AS last_updated,
            DATEDIFF(DAY, STATS_DATE(s.object_id, s.stats_id), GETDATE()) AS days_since_update,
            s.auto_created,
            s.user_created,
            s.no_recompute,
            s.is_temporary
        FROM sys.stats s
        INNER JOIN sys.objects o ON s.object_id = o.object_id
        WHERE o.type = 'U'
        AND STATS_DATE(s.object_id, s.stats_id) IS NOT NULL
        ORDER BY days_since_update DESC
    """,
    
    "Fragmente Indexler": """
        SELECT 
            OBJECT_SCHEMA_NAME(ips.object_id) AS schema_name,
            OBJECT_NAME(ips.object_id) AS table_name,
            i.name AS index_name,
            ips.index_type_desc,
            ips.avg_fragmentation_in_percent,
            ips.page_count,
            ips.avg_page_space_used_in_percent,
            CASE 
                WHEN ips.avg_fragmentation_in_percent > 30 THEN 'REBUILD Önerilir'
                WHEN ips.avg_fragmentation_in_percent > 10 THEN 'REORGANIZE Önerilir'
                ELSE 'OK'
            END AS recommendation
        FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'DETAILED') ips
        INNER JOIN sys.indexes i ON ips.object_id = i.object_id AND ips.index_id = i.index_id
        WHERE ips.avg_fragmentation_in_percent > 5
        AND ips.page_count > 100
        ORDER BY ips.avg_fragmentation_in_percent DESC
    """,
    
    "=== GÜVENLİK ANALİZİ ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Güvenlik Analizi Kategorisi' AS category
    """,
    
    "SQL Server Login'leri": """
        SELECT 
            name AS login_name,
            type_desc AS login_type,
            create_date,
            modify_date,
            is_disabled,
            default_database_name,
            default_language_name,
            CASE 
                WHEN type_desc = 'SQL_LOGIN' THEN 'SQL Server Authentication'
                WHEN type_desc = 'WINDOWS_LOGIN' THEN 'Windows Authentication'
                WHEN type_desc = 'WINDOWS_GROUP' THEN 'Windows Group'
                ELSE type_desc
            END AS authentication_type
        FROM sys.server_principals
        WHERE type IN ('S', 'U', 'G')
        AND name NOT LIKE '##%'
        ORDER BY name
    """,
    
    "Veritabanı Kullanıcıları": """
        SELECT 
            dp.name AS user_name,
            dp.type_desc AS user_type,
            dp.create_date,
            dp.default_schema_name,
            CASE 
                WHEN dp.authentication_type = 0 THEN 'None'
                WHEN dp.authentication_type = 1 THEN 'Instance'
                WHEN dp.authentication_type = 2 THEN 'Database'
                WHEN dp.authentication_type = 3 THEN 'Windows'
            END AS authentication_type,
            sp.name AS login_name
        FROM sys.database_principals dp
        LEFT JOIN sys.server_principals sp ON dp.sid = sp.sid
        WHERE dp.type IN ('S', 'U', 'G')
        AND dp.name NOT IN ('dbo', 'guest', 'INFORMATION_SCHEMA', 'sys')
        ORDER BY dp.name
    """,
    
    "Server Level İzinler": """
        SELECT 
            p.class_desc AS permission_class,
            p.permission_name,
            p.state_desc AS permission_state,
            pr.name AS principal_name,
            pr.type_desc AS principal_type,
            pr2.name AS grantor_name
        FROM sys.server_permissions p
        INNER JOIN sys.server_principals pr ON p.grantee_principal_id = pr.principal_id
        LEFT JOIN sys.server_principals pr2 ON p.grantor_principal_id = pr2.principal_id
        WHERE pr.name NOT LIKE '##%'
        ORDER BY pr.name, p.permission_name
    """,
    
    "Database Level İzinler": """
        SELECT 
            p.class_desc AS permission_class,
            p.permission_name,
            p.state_desc AS permission_state,
            pr.name AS principal_name,
            pr.type_desc AS principal_type,
            pr2.name AS grantor_name,
            OBJECT_NAME(p.major_id) AS object_name
        FROM sys.database_permissions p
        INNER JOIN sys.database_principals pr ON p.grantee_principal_id = pr.principal_id
        LEFT JOIN sys.database_principals pr2 ON p.grantor_principal_id = pr2.principal_id
        WHERE pr.name NOT IN ('dbo', 'guest', 'INFORMATION_SCHEMA', 'sys')
        ORDER BY pr.name, p.permission_name
    """,
    
    "=== YEDEKLEME VE KURTARMA ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Yedekleme ve Kurtarma Kategorisi' AS category
    """,
    
    "Full Backup Geçmişi": """
        -- Not: Bu sorgu msdb veritabanına erişim gerektirir
        SELECT 
            d.name AS database_name,
            b.backup_start_date,
            b.backup_finish_date,
            DATEDIFF(MINUTE, b.backup_start_date, b.backup_finish_date) AS backup_duration_minutes,
            CAST(b.backup_size / 1024.0 / 1024.0 AS DECIMAL(10, 2)) AS backup_size_mb,
            CAST(b.compressed_backup_size / 1024.0 / 1024.0 AS DECIMAL(10, 2)) AS compressed_size_mb,
            b.type AS backup_type,
            b.recovery_model,
            b.server_name,
            b.user_name
        FROM msdb.dbo.backupset b
        INNER JOIN sys.databases d ON b.database_name = d.name
        WHERE b.type = 'D'  -- Full backup
        ORDER BY b.backup_start_date DESC
    """,
    
    "Differential Backup Geçmişi": """
        SELECT 
            d.name AS database_name,
            b.backup_start_date,
            b.backup_finish_date,
            DATEDIFF(MINUTE, b.backup_start_date, b.backup_finish_date) AS backup_duration_minutes,
            CAST(b.backup_size / 1024.0 / 1024.0 AS DECIMAL(10, 2)) AS backup_size_mb,
            CAST(b.compressed_backup_size / 1024.0 / 1024.0 AS DECIMAL(10, 2)) AS compressed_size_mb,
            b.server_name,
            b.user_name
        FROM msdb.dbo.backupset b
        INNER JOIN sys.databases d ON b.database_name = d.name
        WHERE b.type = 'I'  -- Differential backup
        ORDER BY b.backup_start_date DESC
    """,
    
    "Log Backup Geçmişi": """
        SELECT TOP 100
            d.name AS database_name,
            b.backup_start_date,
            b.backup_finish_date,
            DATEDIFF(SECOND, b.backup_start_date, b.backup_finish_date) AS backup_duration_seconds,
            CAST(b.backup_size / 1024.0 / 1024.0 AS DECIMAL(10, 2)) AS backup_size_mb,
            CAST(b.compressed_backup_size / 1024.0 / 1024.0 AS DECIMAL(10, 2)) AS compressed_size_mb,
            b.server_name,
            b.user_name
        FROM msdb.dbo.backupset b
        INNER JOIN sys.databases d ON b.database_name = d.name
        WHERE b.type = 'L'  -- Log backup
        ORDER BY b.backup_start_date DESC
    """,
    
    "=== SQL AGENT VE JOB'LAR ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'SQL Agent ve Job''lar Kategorisi' AS category
    """,
    
    "SQL Agent Job Durumları": """
        SELECT 
            j.name AS job_name,
            j.enabled AS is_enabled,
            j.date_created,
            j.date_modified,
            CASE 
                WHEN jh.run_status = 0 THEN 'Başarısız'
                WHEN jh.run_status = 1 THEN 'Başarılı'
                WHEN jh.run_status = 2 THEN 'Yeniden Deneniyor'
                WHEN jh.run_status = 3 THEN 'İptal Edildi'
                WHEN jh.run_status = 4 THEN 'Çalışıyor'
                ELSE 'Bilinmeyen'
            END AS last_run_status,
            jh.run_date,
            jh.run_time,
            jh.run_duration,
            jh.step_name,
            jh.message
        FROM msdb.dbo.sysjobs j
        LEFT JOIN (
            SELECT 
                job_id,
                run_status,
                run_date,
                run_time,
                run_duration,
                step_name,
                message,
                ROW_NUMBER() OVER (PARTITION BY job_id ORDER BY run_date DESC, run_time DESC) AS rn
            FROM msdb.dbo.sysjobhistory
        ) jh ON j.job_id = jh.job_id AND jh.rn = 1
        ORDER BY j.name
    """,
    
    "Başarısız Job'lar": """
        SELECT 
            j.name AS job_name,
            j.enabled AS is_enabled,
            jh.step_name,
            jh.run_date,
            jh.run_time,
            jh.run_duration,
            jh.message,
            jh.sql_message_id,
            jh.sql_severity
        FROM msdb.dbo.sysjobs j
        INNER JOIN msdb.dbo.sysjobhistory jh ON j.job_id = jh.job_id
        WHERE jh.run_status = 0  -- Başarısız
        AND jh.run_date >= CONVERT(INT, CONVERT(VARCHAR(8), DATEADD(DAY, -7, GETDATE()), 112))
        ORDER BY jh.run_date DESC, jh.run_time DESC
    """,
    
    "Çalışan Job'lar": """
        SELECT 
            j.name AS job_name,
            ja.start_execution_date,
            DATEDIFF(MINUTE, ja.start_execution_date, GETDATE()) AS running_duration_minutes,
            ja.last_executed_step_id,
            ja.last_executed_step_date,
            s.step_name,
            s.subsystem,
            s.command
        FROM msdb.dbo.sysjobs j
        INNER JOIN msdb.dbo.sysjobactivity ja ON j.job_id = ja.job_id
        LEFT JOIN msdb.dbo.sysjobsteps s ON j.job_id = s.job_id AND ja.last_executed_step_id = s.step_id
        WHERE ja.session_id = (SELECT MAX(session_id) FROM msdb.dbo.sysjobactivity)
        AND ja.start_execution_date IS NOT NULL
        AND ja.stop_execution_date IS NULL
        ORDER BY ja.start_execution_date
    """,
    
    "=== ALWAYS ON / AVAILABILITY GROUPS ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Always On / Availability Groups Kategorisi' AS category
    """,
    
    "Availability Groups Durumu": """
        -- Not: Bu sorgu SQL Server 2012+ Enterprise Edition gerektirir
        -- Always On özelliği yoksa sorgu hata verecektir
        SELECT 
            ag.name AS availability_group_name,
            ag.failure_condition_level,
            ag.health_check_timeout,
            ag.primary_replica,
            ag.automated_backup_preference_desc,
            ags.primary_recovery_health_desc,
            ags.secondary_recovery_health_desc,
            ags.synchronization_health_desc
        FROM sys.availability_groups ag
        LEFT JOIN sys.dm_hadr_availability_group_states ags ON ag.group_id = ags.group_id
        ORDER BY ag.name
    """,
    
    "Availability Replicas": """
        SELECT 
            ag.name AS availability_group_name,
            ar.replica_server_name,
            ar.availability_mode_desc,
            ar.failover_mode_desc,
            ar.session_timeout,
            ar.primary_role_allow_connections_desc,
            ar.secondary_role_allow_connections_desc,
            ars.role_desc AS current_role,
            ars.operational_state_desc,
            ars.connected_state_desc,
            ars.synchronization_state_desc,
            ars.synchronization_health_desc
        FROM sys.availability_groups ag
        INNER JOIN sys.availability_replicas ar ON ag.group_id = ar.group_id
        LEFT JOIN sys.dm_hadr_availability_replica_states ars ON ar.replica_id = ars.replica_id
        ORDER BY ag.name, ar.replica_server_name
    """,
    
    "=== REPLICATION DURUMU ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Replication Durumu Kategorisi' AS category
    """,
    
    "Replication Yayıncıları": """
        -- Not: Bu sorgu Replication özelliği ve distribution veritabanı gerektirir
        -- Replication yapılandırılmamışsa sorgu hata verecektir
        SELECT 
            p.publisher_db,
            p.publication,
            p.publication_type,
            p.status,
            p.allow_pull,
            p.allow_push,
            p.allow_anonymous,
            p.immediate_sync,
            p.enabled_for_internet,
            p.allow_sync_tran,
            p.autogen_sync_procs,
            p.retention
        FROM distribution.dbo.MSpublications p
        ORDER BY p.publisher_db, p.publication
    """,
    
    "Replication Aboneleri": """
        SELECT 
            s.publisher_db,
            s.publication,
            s.subscriber_db,
            s.subscriber_server,
            s.subscription_type,
            s.status,
            s.sync_type,
            s.subscription_expiration,
            s.last_sync_date,
            s.last_sync_status,
            s.last_sync_summary
        FROM distribution.dbo.MSsubscriptions s
        ORDER BY s.publisher_db, s.publication, s.subscriber_server
    """,
    
    "=== CONNECTION POOL ANALİZİ ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Connection Pool Analizi Kategorisi' AS category
    """,
    
    "Connection Pool İstatistikleri": """
        SELECT 
            DB_NAME(dbid) AS database_name,
            COUNT(*) AS connection_count,
            SUM(num_reads) AS total_reads,
            SUM(num_writes) AS total_writes,
            SUM(num_reads + num_writes) AS total_io
        FROM sys.sysprocesses
        WHERE dbid > 0
        GROUP BY dbid
        ORDER BY connection_count DESC
    """,
    
    "Uzun Süreli Bağlantılar": """
        SELECT 
            spid,
            DB_NAME(dbid) AS database_name,
            loginame AS login_name,
            hostname AS host_name,
            program_name,
            login_time,
            last_batch,
            DATEDIFF(MINUTE, login_time, GETDATE()) AS connection_duration_minutes,
            DATEDIFF(MINUTE, last_batch, GETDATE()) AS idle_time_minutes,
            status,
            cmd,
            blocked
        FROM sys.sysprocesses
        WHERE spid > 50
        AND DATEDIFF(MINUTE, login_time, GETDATE()) > 60
        ORDER BY connection_duration_minutes DESC
    """,
    
    "=== SCHEMA VE OBJE ANALİZİ ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Schema ve Obje Analizi Kategorisi' AS category
    """,
    
    "Tablo Boyutları ve Satır Sayıları": """
        SELECT 
            t.name AS table_name,
            s.name AS schema_name,
            p.rows AS row_count,
            CAST(SUM(a.total_pages) * 8.0 / 1024 AS DECIMAL(10, 2)) AS total_space_mb,
            CAST(SUM(a.used_pages) * 8.0 / 1024 AS DECIMAL(10, 2)) AS used_space_mb,
            CAST(SUM(a.data_pages) * 8.0 / 1024 AS DECIMAL(10, 2)) AS data_space_mb,
            CAST((SUM(a.total_pages) - SUM(a.used_pages)) * 8.0 / 1024 AS DECIMAL(10, 2)) AS unused_space_mb
        FROM sys.tables t
        INNER JOIN sys.indexes i ON t.object_id = i.object_id
        INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE t.is_ms_shipped = 0
        AND i.object_id > 255
        GROUP BY t.name, s.name, p.rows
        ORDER BY total_space_mb DESC
    """,
    
    "Stored Procedure Listesi": """
        SELECT 
            s.name AS schema_name,
            p.name AS procedure_name,
            p.create_date,
            p.modify_date,
            DATEDIFF(DAY, p.modify_date, GETDATE()) AS days_since_modify,
            p.is_auto_executed,
            p.is_execution_replicated,
            p.is_repl_serializable_only,
            p.skips_repl_commands
        FROM sys.procedures p
        INNER JOIN sys.schemas s ON p.schema_id = s.schema_id
        ORDER BY s.name, p.name
    """,
    
    "View Listesi": """
        SELECT 
            s.name AS schema_name,
            v.name AS view_name,
            v.create_date,
            v.modify_date,
            DATEDIFF(DAY, v.modify_date, GETDATE()) AS days_since_modify,
            v.is_replicated,
            v.has_replication_filter,
            v.has_opaque_metadata,
            v.has_unchecked_assembly_data
        FROM sys.views v
        INNER JOIN sys.schemas s ON v.schema_id = s.schema_id
        ORDER BY s.name, v.name
    """,
    
    "Trigger Listesi": """
        SELECT 
            s.name AS schema_name,
            t.name AS table_name,
            tr.name AS trigger_name,
            tr.create_date,
            tr.modify_date,
            tr.is_disabled,
            tr.is_not_for_replication,
            tr.is_instead_of_trigger,
            tr.parent_class_desc,
            tr.type_desc
        FROM sys.triggers tr
        INNER JOIN sys.objects t ON tr.parent_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE tr.parent_class = 1  -- OBJECT_OR_COLUMN
        ORDER BY s.name, t.name, tr.name
    """,
    
    "=== SİSTEM KAYNAKLARI ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Sistem Kaynakları Kategorisi' AS category
    """,
    
    "CPU Kullanım İstatistikleri": """
        SELECT 
            cpu_id,
            scheduler_id,
            cpu_count,
            hyperthread_ratio,
            physical_cpu_count,
            scheduler_count,
            idle_scheduler_count,
            current_tasks_count,
            runnable_tasks_count,
            current_workers_count,
            active_workers_count,
            work_queue_count,
            pending_disk_io_count
        FROM sys.dm_os_schedulers
        WHERE scheduler_id < 255
        ORDER BY cpu_id
    """,
    
    "Sistem Bellek Detayları": """
        SELECT 
            (total_physical_memory_kb / 1024.0 / 1024.0) AS total_physical_memory_gb,
            (available_physical_memory_kb / 1024.0 / 1024.0) AS available_physical_memory_gb,
            (total_page_file_kb / 1024.0 / 1024.0) AS total_page_file_gb,
            (available_page_file_kb / 1024.0 / 1024.0) AS available_page_file_gb,
            (system_cache_kb / 1024.0 / 1024.0) AS system_cache_gb,
            (kernel_paged_pool_kb / 1024.0 / 1024.0) AS kernel_paged_pool_gb,
            (kernel_nonpaged_pool_kb / 1024.0 / 1024.0) AS kernel_nonpaged_pool_gb,
            (system_memory_state_desc) AS memory_state
        FROM sys.dm_os_sys_memory
    """,
    
    "Network İstatistikleri": """
        SELECT 
            network_adapter,
            bytes_sent,
            bytes_received,
            packets_sent,
            packets_received,
            packets_outbound_errors,
            packets_received_errors
        FROM sys.dm_os_network_interfaces
        ORDER BY bytes_sent + bytes_received DESC
    """,
    
    "=== GELİŞMİŞ İZLEME VE ANALİZ ===": """
        -- Bu bir kategori başlığıdır
        SELECT 'Gelişmiş İzleme ve Analiz Kategorisi' AS category
    """,
    
    "Query Store En Yavaş Sorgular": """
        -- Not: Query Store özelliği SQL Server 2016+ gerektirir
        SELECT TOP 20
            q.query_id,
            qt.query_sql_text,
            rs.count_executions,
            rs.avg_duration / 1000.0 AS avg_duration_ms,
            rs.max_duration / 1000.0 AS max_duration_ms,
            rs.avg_cpu_time / 1000.0 AS avg_cpu_time_ms,
            rs.avg_logical_io_reads,
            rs.avg_logical_io_writes,
            rs.avg_physical_io_reads,
            rs.last_execution_time
        FROM sys.query_store_query q
        INNER JOIN sys.query_store_query_text qt ON q.query_text_id = qt.query_text_id
        INNER JOIN sys.query_store_plan p ON q.query_id = p.query_id
        INNER JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
        ORDER BY rs.avg_duration DESC
    """,
    
    "Query Store Plan Regresyonları": """
        -- Not: Query Store özelliği SQL Server 2016+ gerektirir
        -- Plan değişiklikleri nedeniyle performans düşüşü olan sorgular
        SELECT TOP 20
            q.query_id,
            qt.query_sql_text,
            p.plan_id,
            p.last_compile_start_time,
            rs.avg_duration / 1000.0 AS avg_duration_ms,
            rs.last_duration / 1000.0 AS last_duration_ms,
            rs.count_executions,
            (rs.last_duration - rs.avg_duration) / 1000.0 AS duration_difference_ms
        FROM sys.query_store_query q
        INNER JOIN sys.query_store_query_text qt ON q.query_text_id = qt.query_text_id
        INNER JOIN sys.query_store_plan p ON q.query_id = p.query_id
        INNER JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
        WHERE rs.last_duration > rs.avg_duration * 2  -- Son çalışma ortalamanın 2 katından uzun
        ORDER BY (rs.last_duration - rs.avg_duration) DESC
    """,
    
    "Uzun Süren Transaction'lar": """
        SELECT 
            s.session_id,
            s.login_name,
            s.host_name,
            s.program_name,
            t.transaction_id,
            t.name AS transaction_name,
            t.transaction_begin_time,
            DATEDIFF(SECOND, t.transaction_begin_time, GETDATE()) AS transaction_duration_seconds,
            t.transaction_type,
            CASE t.transaction_state
                WHEN 0 THEN 'Initialized'
                WHEN 1 THEN 'Not Started'
                WHEN 2 THEN 'Active'
                WHEN 3 THEN 'Ended'
                WHEN 4 THEN 'Commit Started'
                WHEN 5 THEN 'Prepared'
                WHEN 6 THEN 'Committed'
                WHEN 7 THEN 'Rolling Back'
                WHEN 8 THEN 'Rolled Back'
            END AS transaction_state,
            (SELECT COUNT(*) FROM sys.dm_tran_locks WHERE request_session_id = s.session_id) AS lock_count
        FROM sys.dm_tran_active_transactions t
        INNER JOIN sys.dm_tran_session_transactions st ON t.transaction_id = st.transaction_id
        INNER JOIN sys.dm_exec_sessions s ON st.session_id = s.session_id
        WHERE DATEDIFF(SECOND, t.transaction_begin_time, GETDATE()) > 30  -- 30 saniyeden uzun
        ORDER BY transaction_duration_seconds DESC
    """,
    
    "Memory Broker Clerks": """
        SELECT 
            type AS clerk_type,
            name AS clerk_name,
            memory_node_id,
            (pages_kb / 1024.0) AS size_mb,
            (virtual_memory_reserved_kb / 1024.0) AS virtual_memory_reserved_mb,
            (virtual_memory_committed_kb / 1024.0) AS virtual_memory_committed_mb,
            (shared_memory_reserved_kb / 1024.0) AS shared_memory_reserved_mb,
            (shared_memory_committed_kb / 1024.0) AS shared_memory_committed_mb
        FROM sys.dm_os_memory_clerks
        WHERE pages_kb > 0
        ORDER BY pages_kb DESC
    """,
    
    "Database Mirror Durumu": """
        -- Not: Database Mirroring yapılandırılmış olmalı
        SELECT 
            DB_NAME(database_id) AS database_name,
            mirroring_state_desc,
            mirroring_role_desc,
            mirroring_safety_level_desc,
            mirroring_partner_name,
            mirroring_partner_instance,
            mirroring_witness_name,
            mirroring_witness_state_desc,
            mirroring_failover_lsn,
            mirroring_connection_timeout,
            mirroring_redo_queue_type
        FROM sys.database_mirroring
        WHERE mirroring_guid IS NOT NULL
        ORDER BY database_name
    """,
    
    "Log Shipping Durumu": """
        -- Not: Log Shipping yapılandırılmış ve msdb erişimi gerektirir
        SELECT 
            primary_server,
            primary_database,
            backup_source_directory,
            backup_destination_directory,
            last_backup_file,
            last_backup_date,
            last_backup_date_utc,
            DATEDIFF(MINUTE, last_backup_date, GETDATE()) AS minutes_since_last_backup,
            backup_threshold,
            is_backup_alert_enabled,
            backup_retention_period
        FROM msdb.dbo.log_shipping_monitor_primary
        ORDER BY last_backup_date DESC
    """,
    
    "Resource Governor Yapılandırması": """
        SELECT 
            pool.name AS resource_pool_name,
            pool.pool_id,
            pool.min_cpu_percent,
            pool.max_cpu_percent,
            pool.min_memory_percent,
            pool.max_memory_percent,
            pool.cap_cpu_percent,
            pool.min_iops_per_volume,
            pool.max_iops_per_volume,
            stats.used_memory_kb / 1024.0 AS used_memory_mb,
            stats.active_memory_grant_count,
            stats.pending_memory_grant_count,
            stats.disk_read_io_throttled_total,
            stats.disk_write_io_throttled_total
        FROM sys.dm_resource_governor_resource_pools pool
        LEFT JOIN sys.dm_resource_governor_resource_pool_volumes stats 
            ON pool.pool_id = stats.pool_id
        ORDER BY pool.pool_id
    """,
    
    "Bekleme Zincirleri (Wait Chains)": """
        SELECT 
            w.blocking_session_id AS blocker_session,
            w.session_id AS blocked_session,
            s1.login_name AS blocker_login,
            s2.login_name AS blocked_login,
            w.wait_type,
            w.wait_duration_ms,
            w.resource_description,
            SUBSTRING(st1.text, (r1.statement_start_offset/2) + 1,
                ((CASE r1.statement_end_offset
                    WHEN -1 THEN DATALENGTH(st1.text)
                    ELSE r1.statement_end_offset
                END - r1.statement_start_offset)/2) + 1) AS blocker_query,
            SUBSTRING(st2.text, (r2.statement_start_offset/2) + 1,
                ((CASE r2.statement_end_offset
                    WHEN -1 THEN DATALENGTH(st2.text)
                    ELSE r2.statement_end_offset
                END - r2.statement_start_offset)/2) + 1) AS blocked_query
        FROM sys.dm_os_waiting_tasks w
        INNER JOIN sys.dm_exec_sessions s1 ON w.blocking_session_id = s1.session_id
        INNER JOIN sys.dm_exec_sessions s2 ON w.session_id = s2.session_id
        LEFT JOIN sys.dm_exec_requests r1 ON w.blocking_session_id = r1.session_id
        LEFT JOIN sys.dm_exec_requests r2 ON w.session_id = r2.session_id
        OUTER APPLY sys.dm_exec_sql_text(r1.sql_handle) st1
        OUTER APPLY sys.dm_exec_sql_text(r2.sql_handle) st2
        WHERE w.blocking_session_id > 0
        ORDER BY w.wait_duration_ms DESC
    """,
    
    "VLF (Virtual Log File) Sayısı": """
        -- Yüksek VLF sayısı performans sorunlarına yol açabilir
        CREATE TABLE #VLFInfo (
            RecoveryUnitId INT,
            FileId INT,
            FileSize BIGINT,
            StartOffset BIGINT,
            FSeqNo BIGINT,
            Status BIGINT,
            Parity BIGINT,
            CreateLSN NUMERIC(38)
        );
        
        INSERT INTO #VLFInfo
        EXEC sp_executesql N'DBCC LOGINFO WITH NO_INFOMSGS';
        
        SELECT 
            DB_NAME() AS database_name,
            COUNT(*) AS vlf_count,
            CASE 
                WHEN COUNT(*) > 500 THEN 'Çok Yüksek - Acil Müdahale Gerekli'
                WHEN COUNT(*) > 200 THEN 'Yüksek - Optimizasyon Önerilir'
                WHEN COUNT(*) > 100 THEN 'Orta - İzleme Gerekli'
                ELSE 'Normal'
            END AS status,
            CAST(SUM(FileSize) / 1024.0 / 1024.0 AS DECIMAL(10, 2)) AS total_log_size_mb
        FROM #VLFInfo;
        
        DROP TABLE #VLFInfo;
    """,
    
    "Columnstore Index Analizleri": """
        SELECT 
            OBJECT_SCHEMA_NAME(i.object_id) AS schema_name,
            OBJECT_NAME(i.object_id) AS table_name,
            i.name AS index_name,
            i.type_desc AS index_type,
            p.partition_number,
            rg.state_desc AS rowgroup_state,
            rg.total_rows,
            rg.deleted_rows,
            rg.size_in_bytes / 1024.0 / 1024.0 AS size_mb,
            (rg.deleted_rows * 100.0 / NULLIF(rg.total_rows, 0)) AS deleted_rows_percent
        FROM sys.indexes i
        INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        INNER JOIN sys.column_store_row_groups rg ON p.partition_number = rg.partition_number 
            AND i.object_id = rg.object_id AND i.index_id = rg.index_id
        WHERE i.type IN (5, 6)  -- Clustered/Non-clustered Columnstore
        ORDER BY schema_name, table_name, partition_number
    """,
    
    "Tempdb Contention Analizi": """
        SELECT 
            session_id,
            wait_type,
            wait_duration_ms,
            blocking_session_id,
            resource_description,
            SUBSTRING(qt.text, (er.statement_start_offset/2) + 1,
                ((CASE er.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE er.statement_end_offset
                END - er.statement_start_offset)/2) + 1) AS query_text
        FROM sys.dm_os_waiting_tasks wt
        INNER JOIN sys.dm_exec_requests er ON wt.session_id = er.session_id
        CROSS APPLY sys.dm_exec_sql_text(er.sql_handle) qt
        WHERE wt.wait_type LIKE 'PAGE%LATCH%'
        AND resource_description LIKE '2:%'  -- TempDB
        ORDER BY wait_duration_ms DESC
    """,
    
    "Missing Statistics": """
        SELECT 
            OBJECT_SCHEMA_NAME(object_id) AS schema_name,
            OBJECT_NAME(object_id) AS table_name,
            column_id,
            COL_NAME(object_id, column_id) AS column_name,
            'CREATE STATISTICS [STAT_' + OBJECT_NAME(object_id) + '_' + 
                COL_NAME(object_id, column_id) + '] ON [' + 
                OBJECT_SCHEMA_NAME(object_id) + '].[' + 
                OBJECT_NAME(object_id) + '] ([' + 
                COL_NAME(object_id, column_id) + '])' AS create_stat_statement
        FROM sys.dm_db_missing_index_details d
        CROSS APPLY sys.dm_db_missing_index_columns(d.index_handle)
        WHERE d.database_id = DB_ID()
        AND column_usage = 'EQUALITY'
        AND NOT EXISTS (
            SELECT 1 
            FROM sys.stats_columns sc
            INNER JOIN sys.stats s ON sc.object_id = s.object_id AND sc.stats_id = s.stats_id
            WHERE sc.object_id = d.object_id 
            AND sc.column_id = sys.dm_db_missing_index_columns.column_id
            AND sc.stats_column_id = 1
        )
        ORDER BY schema_name, table_name, column_name
    """,
    
    "Top CPU Kullanan Planlar": """
        SELECT TOP 20
            qs.query_hash,
            COUNT(*) AS plan_count,
            SUM(qs.execution_count) AS total_execution_count,
            SUM(qs.total_worker_time) / 1000000.0 AS total_cpu_seconds,
            SUM(qs.total_worker_time) / SUM(qs.execution_count) / 1000.0 AS avg_cpu_ms,
            MIN(qs.statement_start_offset) AS statement_start_offset,
            MIN(qs.statement_end_offset) AS statement_end_offset,
            (SELECT TOP 1 text FROM sys.dm_exec_sql_text(MIN(qs.sql_handle))) AS sample_query_text
        FROM sys.dm_exec_query_stats qs
        GROUP BY qs.query_hash
        ORDER BY total_cpu_seconds DESC
    """,
    
    "Read/Write Latency Analizi": """
        SELECT 
            DB_NAME(database_id) AS database_name,
            file_id,
            io_stall_read_ms,
            num_of_reads,
            CAST(io_stall_read_ms / NULLIF(num_of_reads, 0) AS DECIMAL(10, 2)) AS avg_read_latency_ms,
            io_stall_write_ms,
            num_of_writes,
            CAST(io_stall_write_ms / NULLIF(num_of_writes, 0) AS DECIMAL(10, 2)) AS avg_write_latency_ms,
            io_stall_queued_read_ms,
            io_stall_queued_write_ms,
            CASE 
                WHEN CAST(io_stall_read_ms / NULLIF(num_of_reads, 0) AS DECIMAL(10, 2)) > 20 THEN 'Yavaş Okuma'
                WHEN CAST(io_stall_write_ms / NULLIF(num_of_writes, 0) AS DECIMAL(10, 2)) > 20 THEN 'Yavaş Yazma'
                ELSE 'Normal'
            END AS status
        FROM sys.dm_io_virtual_file_stats(NULL, NULL)
        WHERE num_of_reads > 0 OR num_of_writes > 0
        ORDER BY 
            CAST(io_stall_read_ms / NULLIF(num_of_reads, 0) AS DECIMAL(10, 2)) + 
            CAST(io_stall_write_ms / NULLIF(num_of_writes, 0) AS DECIMAL(10, 2)) DESC
    """,
    
    "Database Mail Queue": """
        -- Not: Database Mail yapılandırılmış olmalı
        SELECT 
            mailitem_id,
            profile_id,
            recipients,
            copy_recipients,
            blind_copy_recipients,
            subject,
            body,
            body_format,
            importance,
            sensitivity,
            file_attachments,
            attachment_encoding,
            query,
            send_request_date,
            send_request_user,
            sent_status,
            CASE sent_status
                WHEN 0 THEN 'Gönderilmedi'
                WHEN 1 THEN 'Gönderildi'
                WHEN 2 THEN 'Başarısız'
                WHEN 3 THEN 'Yeniden Deneniyor'
            END AS status_description
        FROM msdb.dbo.sysmail_allitems
        WHERE send_request_date >= DATEADD(DAY, -7, GETDATE())
        ORDER BY send_request_date DESC
    """,
    
    "Database Encryption Key Durumu": """
        -- Not: TDE (Transparent Data Encryption) yapılandırılmış olmalı
        SELECT 
            DB_NAME(e.database_id) AS database_name,
            e.encryption_state,
            CASE e.encryption_state
                WHEN 0 THEN 'Şifreleme Yok'
                WHEN 1 THEN 'Şifrelenmemiş'
                WHEN 2 THEN 'Şifreleme Devam Ediyor'
                WHEN 3 THEN 'Şifrelenmiş'
                WHEN 4 THEN 'Key Değişimi Devam Ediyor'
                WHEN 5 THEN 'Şifre Çözme Devam Ediyor'
                WHEN 6 THEN 'Koruma Değişimi Devam Ediyor'
            END AS encryption_state_desc,
            e.key_algorithm,
            e.key_length,
            e.encryptor_type,
            c.name AS certificate_name,
            c.subject,
            c.expiry_date,
            DATEDIFF(DAY, GETDATE(), c.expiry_date) AS days_until_expiry,
            e.encryption_scan_state,
            e.encryption_scan_modify_date,
            e.percent_complete
        FROM sys.dm_database_encryption_keys e
        LEFT JOIN sys.certificates c ON e.encryptor_thumbprint = c.thumbprint
        ORDER BY database_name
    """
}


def load_user_queries():
    """Kullanıcı sorgularını yükle"""
    user_queries = {}
    try:
        if os.path.exists(USER_QUERIES_FILE):
            with open(USER_QUERIES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Eski format desteği (string olarak kaydedilmiş sorgular)
                for key, value in data.items():
                    if isinstance(value, str):
                        # Eski format - sadece sorgu metni
                        user_queries[key] = {
                            "query": value,
                            "category": "Kullanıcı Sorguları"
                        }
                    else:
                        # Yeni format - kategori ile birlikte
                        user_queries[key] = value
    except Exception as e:
        print(f"Kullanıcı sorguları yüklenirken hata: {e}")
    return user_queries


def save_user_query(name: str, query: str, category: str = "Kullanıcı Sorguları"):
    """Kullanıcı sorgusunu kaydet"""
    try:
        user_queries = load_user_queries()
        
        # Sorguyu kategori ile birlikte kaydet
        user_queries[name] = {
            "query": query,
            "category": category
        }
        
        with open(USER_QUERIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_queries, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Kullanıcı sorgusu kaydedilirken hata: {e}")
        return False


def delete_user_query(name: str):
    """Kullanıcı sorgusunu sil"""
    try:
        user_queries = load_user_queries()
        if name in user_queries:
            del user_queries[name]
            
            with open(USER_QUERIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_queries, f, indent=4, ensure_ascii=False)
            
            return True
    except Exception as e:
        print(f"Kullanıcı sorgusu silinirken hata: {e}")
    return False


def rename_user_query(old_name: str, new_name: str):
    """Kullanıcı sorgusunun ismini değiştir"""
    try:
        user_queries = load_user_queries()
        if old_name in user_queries:
            if new_name in user_queries:
                return False  # Yeni isim zaten var
            
            query = user_queries[old_name]
            del user_queries[old_name]
            user_queries[new_name] = query
            
            with open(USER_QUERIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_queries, f, indent=4, ensure_ascii=False)
            
            return True
    except Exception as e:
        print(f"Kullanıcı sorgusu ismi değiştirilirken hata: {e}")
    return False


def get_all_queries():
    """Tüm sorguları (hazır + kullanıcı) döndür"""
    all_queries = PREDEFINED_QUERIES.copy()
    user_queries = load_user_queries()
    
    # Kullanıcı sorgularını ekle (sadece sorgu metinlerini)
    for name, data in user_queries.items():
        if isinstance(data, dict):
            all_queries[name] = data.get("query", "")
        else:
            all_queries[name] = data
    
    return all_queries


def get_user_query_categories():
    """Kullanıcı sorgularının kategorilerini döndür"""
    user_queries = load_user_queries()
    categories = set()
    
    for name, data in user_queries.items():
        if isinstance(data, dict):
            category = data.get("category", "Kullanıcı Sorguları")
            categories.add(category)
    
    return sorted(list(categories))

