-- Auto-generated PostgreSQL schema from SQLite DDL
-- Do not edit by hand; run scripts/generate_postgresql_schema.py
BEGIN;
CREATE TABLE IF NOT EXISTS base_bom (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS base_customer (
        id SERIAL PRIMARY KEY,
        customer_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        contact TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        credit_limit REAL DEFAULT 0,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS base_defect (
        id SERIAL PRIMARY KEY,
        defect_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        defect_type TEXT,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS base_material (id SERIAL PRIMARY KEY, material_no TEXT UNIQUE, material_name TEXT, specification TEXT, unit TEXT, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS base_process (
        id SERIAL PRIMARY KEY,
        process_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        workshop_id INTEGER,
        description TEXT,
        standard_time REAL,
        sort_order INTEGER DEFAULT 0,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS base_process_route (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL,
        route_name TEXT NOT NULL,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "workshop_id" INTEGER, "version" INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS base_process_route_detail (
        id SERIAL PRIMARY KEY,
        route_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        standard_time REAL,
        description TEXT, "workshop_id" INTEGER, "is_inspection_point" INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS base_product (
        id SERIAL PRIMARY KEY,
        product_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        specification TEXT,
        unit TEXT,
        product_type TEXT,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS base_salary_config (
        id SERIAL PRIMARY KEY,
        process_id INTEGER,
        base_salary REAL DEFAULT 0,
        piece_rate REAL DEFAULT 0,
        overtime_rate REAL DEFAULT 0,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS base_stage_code (
            id SERIAL PRIMARY KEY, stage_name TEXT NOT NULL,
            code TEXT UNIQUE, color TEXT, description TEXT,
            sort_order INTEGER DEFAULT 0, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS base_standard_cost (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL,
        material_cost REAL DEFAULT 0,
        labor_cost REAL DEFAULT 0,
        overhead_cost REAL DEFAULT 0,
        total_cost REAL DEFAULT 0,
        effective_date TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS base_station_config (id SERIAL PRIMARY KEY, station TEXT UNIQUE, station_name TEXT, process_id INTEGER, sequence_no INTEGER DEFAULT 0, allow_repeat INTEGER DEFAULT 0, previous_station TEXT, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, required_sn INTEGER DEFAULT 0, required_material INTEGER DEFAULT 0, check_sequence INTEGER DEFAULT 0, prev_station INTEGER DEFAULT 0, required_process TEXT);
CREATE TABLE IF NOT EXISTS base_supplier (
        id SERIAL PRIMARY KEY,
        supplier_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        contact TEXT,
        phone TEXT,
        address TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS base_unit (
        id SERIAL PRIMARY KEY,
        unit_name TEXT NOT NULL,
        unit_symbol TEXT NOT NULL,
        status INTEGER DEFAULT 1
    );
CREATE TABLE IF NOT EXISTS base_workshop (
        id SERIAL PRIMARY KEY,
        workshop_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS base_workstation (id SERIAL PRIMARY KEY, station_name TEXT, workstation_name TEXT, code TEXT UNIQUE, workshop_id INTEGER, process_id INTEGER, location TEXT, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS eqp_check_item (
        id SERIAL PRIMARY KEY,
        item_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        standard TEXT,
        method TEXT,
        check_type TEXT,
        status INTEGER DEFAULT 1
    );
CREATE TABLE IF NOT EXISTS eqp_check_project (
        id SERIAL PRIMARY KEY,
        project_name TEXT NOT NULL,
        check_type TEXT,
        standard TEXT,
        method TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS eqp_check_workorder (
        id SERIAL PRIMARY KEY,
        workorder_no TEXT NOT NULL UNIQUE,
        plan_id INTEGER NOT NULL,
        equipment_id INTEGER NOT NULL,
        check_result TEXT,
        status INTEGER DEFAULT 0,
        assigned_to INTEGER,
        check_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS eqp_fixture (
            id SERIAL PRIMARY KEY, fixture_name TEXT,
            code TEXT UNIQUE, process_id INTEGER, specification TEXT,
            quantity INTEGER DEFAULT 0, location TEXT, status INTEGER DEFAULT 1,
            remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS eqp_ledger (
        id SERIAL PRIMARY KEY,
        equipment_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        type_id INTEGER,
        model TEXT,
        manufacturer TEXT,
        purchase_date TEXT,
        workshop_id INTEGER,
        location TEXT,
        status INTEGER DEFAULT 1,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS eqp_maintenance_plan (
        id SERIAL PRIMARY KEY,
        plan_name TEXT NOT NULL,
        equipment_id INTEGER NOT NULL,
        check_items TEXT,
        frequency TEXT,
        next_date TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS eqp_mold (
            id SERIAL PRIMARY KEY, mold_name TEXT, code TEXT UNIQUE,
            product_id INTEGER, specification TEXT, cavity_count INTEGER,
            usage_count INTEGER DEFAULT 0, max_usage INTEGER DEFAULT 0,
            location TEXT, status INTEGER DEFAULT 1, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS eqp_repair_order (
        id SERIAL PRIMARY KEY,
        repair_no TEXT NOT NULL UNIQUE,
        equipment_id INTEGER NOT NULL,
        fault_desc TEXT,
        repair_desc TEXT,
        reporter INTEGER,
        repairer INTEGER,
        status INTEGER DEFAULT 0,
        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        repair_time TIMESTAMP,
        remark TEXT);
CREATE TABLE IF NOT EXISTS eqp_type (
        id SERIAL PRIMARY KEY,
        type_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1
    );
CREATE TABLE IF NOT EXISTS flow_definition (
        id SERIAL PRIMARY KEY,
        flow_name TEXT NOT NULL,
        flow_key TEXT NOT NULL UNIQUE,
        description TEXT,
        steps TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS flow_instance (
        id SERIAL PRIMARY KEY,
        flow_id INTEGER NOT NULL,
        biz_type TEXT,
        biz_id INTEGER,
        title TEXT,
        current_step INTEGER DEFAULT 1,
        status INTEGER DEFAULT 0,
        creator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "steps_snapshot" TEXT);
CREATE TABLE IF NOT EXISTS flow_task (
        id SERIAL PRIMARY KEY,
        instance_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        assignee INTEGER NOT NULL,
        action TEXT,
        comment TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS hr_skill_matrix (id SERIAL PRIMARY KEY, user_id INTEGER, process_id INTEGER, skill_level INTEGER DEFAULT 0, certified INTEGER DEFAULT 0, certified_at TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS hr_training (id SERIAL PRIMARY KEY, training_name TEXT, training_type TEXT, trainer TEXT, start_date TEXT, end_date TEXT, location TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS hr_training_record (id SERIAL PRIMARY KEY, training_id INTEGER, user_id INTEGER, score REAL, result TEXT, certificate TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_area (
        id SERIAL PRIMARY KEY,
        warehouse_id INTEGER NOT NULL,
        area_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_arrival_notice (
        id SERIAL PRIMARY KEY,
        notice_no TEXT NOT NULL UNIQUE,
        supplier_id INTEGER,
        status INTEGER DEFAULT 0,
        expected_date TEXT,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , "purchase_order_id" INTEGER, "delivery_note_no" TEXT, "arrived_at" TIMESTAMP, "exception_code" TEXT, "exception_reason" TEXT, "created_by" INTEGER, "updated_at" TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_arrival_notice_item (
        id SERIAL PRIMARY KEY,
        notice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL, "purchase_order_item_id" INTEGER, "arrived_qty" REAL, "normal_qty" REAL, "excess_qty" REAL, "accepted_qty" REAL, "returned_qty" REAL, "pending_qty" REAL, "inspection_mode" TEXT, "created_at" TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_balance (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL UNIQUE,
        quantity REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_batch (id SERIAL PRIMARY KEY, batch_no TEXT UNIQUE, product_id INTEGER, supplier TEXT, quantity REAL DEFAULT 0, production_date TEXT, expiry_date TEXT, status INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_inbound (
        id SERIAL PRIMARY KEY,
        inbound_no TEXT NOT NULL UNIQUE,
        inbound_type TEXT,
        supplier TEXT,
        total_amount REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS inv_inbound_item (
        id SERIAL PRIMARY KEY,
        inbound_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        remark TEXT);
CREATE TABLE IF NOT EXISTS inv_line_warehouse (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL,
        workshop_id INTEGER,
        quantity REAL DEFAULT 0,
        min_quantity REAL DEFAULT 10,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_location (
        id SERIAL PRIMARY KEY,
        area_id INTEGER NOT NULL,
        location_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_outbound (
        id SERIAL PRIMARY KEY,
        outbound_no TEXT NOT NULL UNIQUE,
        outbound_type TEXT,
        customer TEXT,
        total_amount REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS inv_outbound_item (
        id SERIAL PRIMARY KEY,
        outbound_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        remark TEXT);
CREATE TABLE IF NOT EXISTS inv_receipt_action (
            id SERIAL PRIMARY KEY,
            arrival_item_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            reason TEXT,
            operator_id INTEGER NOT NULL,
            client_operation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_receipt_posting (
            id SERIAL PRIMARY KEY,
            posting_no TEXT NOT NULL UNIQUE,
            arrival_item_id INTEGER NOT NULL,
            inspection_id INTEGER,
            product_id INTEGER NOT NULL,
            warehouse_id INTEGER NOT NULL,
            area_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL,
            quantity REAL NOT NULL,
            operator_id INTEGER NOT NULL,
            client_operation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_stock_balance (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            warehouse_id INTEGER NOT NULL,
            area_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_trace (id SERIAL PRIMARY KEY, batch_id INTEGER, trace_type TEXT, biz_no TEXT, operation TEXT, ref_no TEXT, ref_id INTEGER, quantity REAL DEFAULT 0, operator INTEGER, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_transaction (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL,
        trans_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        balance REAL NOT NULL,
        ref_no TEXT,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inv_transaction_log (
        id SERIAL PRIMARY KEY,
        trans_type TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        warehouse_id INTEGER,
        area_id INTEGER,
        location_id INTEGER,
        batch_no TEXT,
        ref_no TEXT,
        ref_type TEXT,
        operator INTEGER,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS inv_warehouse (
        id SERIAL PRIMARY KEY,
        warehouse_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        address TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS iot_aim_device_sequence (
        endpoint_id INTEGER NOT NULL,
        device_code TEXT NOT NULL,
        lifecycle_id TEXT NOT NULL,
        last_sequence INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(endpoint_id, device_code, lifecycle_id)
    );
CREATE TABLE IF NOT EXISTS iot_aim_event_outbox (
        event_id TEXT PRIMARY KEY,
        envelope_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        dispatched_at TIMESTAMP
    , dispatch_owner TEXT, dispatch_until INTEGER);
CREATE TABLE IF NOT EXISTS iot_device_alarm (
        event_id TEXT PRIMARY KEY, factory_code TEXT NOT NULL, device_code TEXT NOT NULL,
        lifecycle_id TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS iot_device_command (
        id SERIAL PRIMARY KEY,
        command_id TEXT NOT NULL UNIQUE,
        factory_code TEXT NOT NULL,
        gateway_code TEXT NOT NULL,
        device_code TEXT NOT NULL,
        command_type TEXT NOT NULL,
        command_json TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'queued'
          CHECK(status IN ('queued','leased','acknowledged','failed','expired')),
        attempts INTEGER NOT NULL DEFAULT 0,
        lease_owner TEXT, lease_token TEXT, lease_until INTEGER,
        last_error TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS iot_device_cursor (
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL,
        last_sequence INTEGER NOT NULL CHECK(last_sequence > 0),
        last_event_id TEXT NOT NULL, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(factory_code,device_code)
    );
CREATE TABLE IF NOT EXISTS iot_device_cursor_v2 (
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        last_sequence INTEGER NOT NULL CHECK(last_sequence > 0), last_event_id TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(factory_code,device_code,lifecycle_id)
    );
CREATE TABLE IF NOT EXISTS iot_device_event (
        id SERIAL PRIMARY KEY,
        event_id TEXT NOT NULL UNIQUE,
        schema_version TEXT NOT NULL,
        customer_code TEXT NOT NULL,
        factory_code TEXT NOT NULL,
        gateway_code TEXT NOT NULL,
        device_code TEXT NOT NULL,
        event_type TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        received_at TEXT,
        sequence INTEGER NOT NULL CHECK(sequence > 0),
        correlation_id TEXT,
        payload_json TEXT NOT NULL,
        raw_reference TEXT,
        lifecycle_id TEXT NOT NULL DEFAULT 'legacy',
        processing_status TEXT NOT NULL DEFAULT 'pending',
        ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    , processing_attempts INTEGER NOT NULL DEFAULT 0, last_processing_error TEXT, next_processing_at INTEGER NOT NULL DEFAULT 0, processing_lease_owner TEXT, processing_lease_until INTEGER, processing_lease_token TEXT, processed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS iot_device_event_conflict (
        id SERIAL PRIMARY KEY, event_id TEXT NOT NULL,
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        sequence INTEGER NOT NULL, payload_json TEXT NOT NULL, reason TEXT NOT NULL,
        quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(event_id,reason)
    );
CREATE TABLE IF NOT EXISTS iot_device_event_effect (
        event_id TEXT PRIMARY KEY,
        effect_type TEXT NOT NULL,
        effect_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS iot_device_measurement (
        event_id TEXT PRIMARY KEY, factory_code TEXT NOT NULL, device_code TEXT NOT NULL,
        lifecycle_id TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
        occurred_at TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS iot_device_sequence_gap (
        id SERIAL PRIMARY KEY, factory_code TEXT NOT NULL,
        device_code TEXT NOT NULL, missing_from INTEGER NOT NULL, missing_to INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),
        detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP,
        UNIQUE(factory_code,device_code,missing_from,missing_to)
    );
CREATE TABLE IF NOT EXISTS iot_device_sequence_gap_v2 (
        id SERIAL PRIMARY KEY, factory_code TEXT NOT NULL,
        device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        missing_from INTEGER NOT NULL, missing_to INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP,
        UNIQUE(factory_code,device_code,lifecycle_id,missing_from,missing_to)
    );
CREATE TABLE IF NOT EXISTS iot_device_state (
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        state TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(factory_code,device_code,lifecycle_id)
    );
CREATE TABLE IF NOT EXISTS iot_gateway_credential (
        id SERIAL PRIMARY KEY,
        gateway_code TEXT NOT NULL UNIQUE,
        secret_hash TEXT,
        secret_fingerprint TEXT,
        customer_code TEXT,
        factory_code TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS iot_gateway_nonce (
        id SERIAL PRIMARY KEY,
        gateway_code TEXT NOT NULL,
        nonce TEXT NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at INTEGER,
        UNIQUE(gateway_code,nonce)
    );
CREATE TABLE IF NOT EXISTS iot_inspection_report (
        id SERIAL PRIMARY KEY,
        request_id INTEGER NOT NULL,
        endpoint_id INTEGER NOT NULL,
        sn TEXT NOT NULL,
        inspected_at TIMESTAMP NOT NULL,
        result TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        archive_path TEXT,
        file_hash TEXT NOT NULL,
        import_status TEXT NOT NULL DEFAULT 'imported',
        failure_reason TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        prod_report_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS iot_inspection_value (
        id SERIAL PRIMARY KEY,
        report_id INTEGER NOT NULL,
        item_code TEXT NOT NULL,
        item_name TEXT,
        measured_value TEXT,
        unit TEXT,
        lower_limit REAL,
        upper_limit REAL,
        result TEXT);
CREATE TABLE IF NOT EXISTS iot_machine_endpoint (
        id SERIAL PRIMARY KEY,
        equipment_id INTEGER NOT NULL,
        protocol_version INTEGER NOT NULL DEFAULT 1,
        transport_mode TEXT NOT NULL DEFAULT 'server',
        bind_ip TEXT NOT NULL,
        allowed_remote_ip TEXT,
        listen_port INTEGER NOT NULL,
        reader_ip TEXT,
        reader_port INTEGER,
        reader_frame_idle_ms INTEGER NOT NULL DEFAULT 80,
        station_code TEXT NOT NULL,
        process_id INTEGER NOT NULL,
        cavity_code TEXT NOT NULL DEFAULT '1',
        encoding TEXT NOT NULL DEFAULT 'utf-8',
        timeout_ms INTEGER NOT NULL DEFAULT 1000,
        heartbeat_seconds INTEGER NOT NULL DEFAULT 30,
        laser_template TEXT,
        inspection_template TEXT,
         shared_secret TEXT,
         lifecycle_id TEXT NOT NULL DEFAULT 'legacy',
         require_request_nonce INTEGER NOT NULL DEFAULT 0,
        csv_input_dir TEXT,
        csv_stable_seconds INTEGER NOT NULL DEFAULT 2,
        enabled INTEGER NOT NULL DEFAULT 1,
        last_seen_at TIMESTAMP,
        last_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "listener_status" TEXT NOT NULL DEFAULT 'stopped', "listener_pid" INTEGER, "listener_started_at" TIMESTAMP, "csv_last_scan_at" TIMESTAMP, "csv_last_error" TEXT);
CREATE TABLE IF NOT EXISTS iot_machine_request (
        id SERIAL PRIMARY KEY,
        endpoint_id INTEGER NOT NULL,
        session_id INTEGER,
        request_no TEXT NOT NULL,
        protocol_version INTEGER NOT NULL,
        station_code TEXT NOT NULL,
        cavity_code TEXT NOT NULL,
        sn TEXT NOT NULL,
        workorder_id INTEGER,
        task_id INTEGER,
        route_step_id INTEGER,
        decision TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        reason_message TEXT,
        laser_template TEXT,
        inspection_template TEXT,
        elapsed_ms INTEGER NOT NULL DEFAULT 0,
        dedupe_key TEXT NOT NULL,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        report_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS iot_machine_runtime (
        component TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        pid INTEGER,
        started_at TIMESTAMP,
        heartbeat_at TIMESTAMP,
        last_error TEXT
    );
CREATE TABLE IF NOT EXISTS iot_machine_session (
        id SERIAL PRIMARY KEY,
        endpoint_id INTEGER NOT NULL,
        remote_address TEXT,
        connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_heartbeat_at TIMESTAMP,
        disconnected_at TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'online',
        request_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT);
CREATE TABLE IF NOT EXISTS job_config (
        id SERIAL PRIMARY KEY,
        job_name TEXT NOT NULL,
        job_key TEXT NOT NULL UNIQUE,
        cron_expression TEXT,
        job_class TEXT,
        params TEXT,
        status INTEGER DEFAULT 1,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS job_log (
        id SERIAL PRIMARY KEY,
        job_id INTEGER NOT NULL,
        job_name TEXT,
        status INTEGER,
        message TEXT,
        cost_time INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_andon (id SERIAL PRIMARY KEY, andon_no TEXT UNIQUE, workstation_id INTEGER, andon_type TEXT, description TEXT, caller INTEGER, responder INTEGER, response_time TEXT, resolve_time TEXT, close_time TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "priority" INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS prod_batch (
        id SERIAL PRIMARY KEY,
        batch_no TEXT NOT NULL,
        plan_id INTEGER,
        plan_item_id INTEGER NOT NULL,
        sales_order_id INTEGER,
        product_id INTEGER NOT NULL,
        workshop_id INTEGER NOT NULL,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        defect_qty REAL DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(plan_item_id, batch_no));
CREATE TABLE IF NOT EXISTS prod_box (id SERIAL PRIMARY KEY, box_no TEXT UNIQUE, product_id INTEGER, workorder_id INTEGER, quantity REAL DEFAULT 0, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "box_type" TEXT, "sn_list" TEXT);
CREATE TABLE IF NOT EXISTS prod_cost (
            id SERIAL PRIMARY KEY, workorder_id INTEGER,
            cost_type TEXT, amount REAL DEFAULT 0, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS prod_defect_receive (
        id SERIAL PRIMARY KEY,
        receive_no TEXT NOT NULL UNIQUE,
        sn TEXT,
        product_id INTEGER,
        defect_id INTEGER,
        station TEXT,
        quantity INTEGER DEFAULT 1,
        process_type TEXT DEFAULT '待处理',
        operator INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS prod_exception (
        id SERIAL PRIMARY KEY,
        exception_no TEXT NOT NULL UNIQUE,
        exception_type TEXT,
        station TEXT,
        description TEXT,
        severity TEXT DEFAULT 'medium',
        handler INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS prod_labor_time (id SERIAL PRIMARY KEY, user_id INTEGER, task_id INTEGER, workorder_id INTEGER, work_date TEXT, duration REAL DEFAULT 0, overtime REAL DEFAULT 0, quantity REAL DEFAULT 0, amount REAL DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_material_lock (id SERIAL PRIMARY KEY, material_id INTEGER, reason TEXT, operator INTEGER, status INTEGER DEFAULT 1, unlock_time TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "lock_no" TEXT, "lock_type" TEXT, "released_at" TEXT);
CREATE TABLE IF NOT EXISTS prod_material_req (
        id SERIAL PRIMARY KEY,
        req_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        req_type TEXT DEFAULT '领料',
        status INTEGER DEFAULT 0,
        operator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , "production_batch_id" INTEGER, "bom_snapshot_id" INTEGER, "required_qty" REAL DEFAULT 0, "requested_qty" REAL DEFAULT 0, "issued_qty" REAL DEFAULT 0, "received_qty" REAL DEFAULT 0, "returned_qty" REAL DEFAULT 0, "warehouse_id" INTEGER, "location_id" INTEGER, "material_batch_no" TEXT, "remark" TEXT, "issued_by" INTEGER, "received_by" INTEGER, "issued_at" TIMESTAMP, "received_at" TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_outsource (id SERIAL PRIMARY KEY, outsource_no TEXT UNIQUE, supplier_id INTEGER, product_id INTEGER, quantity REAL DEFAULT 0, unit_price REAL DEFAULT 0, amount REAL DEFAULT 0, delivery_date TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_packing (id SERIAL PRIMARY KEY, packing_no TEXT UNIQUE, workorder_id INTEGER, package_type TEXT, quantity REAL DEFAULT 0, operator INTEGER, packed_at TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_plan (
        id SERIAL PRIMARY KEY,
        plan_no TEXT NOT NULL UNIQUE,
        sales_order_id INTEGER,
        plan_type TEXT,
        start_date TEXT,
        end_date TEXT,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS prod_plan_item (
        id SERIAL PRIMARY KEY,
        plan_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        workshop_id INTEGER,
        remark TEXT, "sales_order_item_id" INTEGER);
CREATE TABLE IF NOT EXISTS prod_quality_disposition (
            id SERIAL PRIMARY KEY,
            disposition_no TEXT NOT NULL UNIQUE,
            sn TEXT NOT NULL,
            inspection_report_id INTEGER UNIQUE,
            machine_request_id INTEGER,
            prod_report_id INTEGER,
            workorder_id INTEGER NOT NULL,
            source_task_id INTEGER NOT NULL,
            route_step_id INTEGER NOT NULL,
            action TEXT NOT NULL DEFAULT 'pending',
            status TEXT NOT NULL DEFAULT 'pending_review',
            rework_task_id INTEGER,
            cycle_no INTEGER NOT NULL DEFAULT 1,
            reason TEXT,
            reviewer_id INTEGER,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_report (
        id SERIAL PRIMARY KEY,
        report_no TEXT NOT NULL UNIQUE,
        task_id INTEGER NOT NULL,
        workorder_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        qualified_qty REAL NOT NULL,
        defect_qty REAL DEFAULT 0,
        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        remark TEXT,
        client_operation_id TEXT, "production_batch_id" INTEGER, "approval_status" INTEGER DEFAULT 0, "defect_id" INTEGER, "posted_at" TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_rework (id SERIAL PRIMARY KEY, rework_no TEXT UNIQUE, workorder_id INTEGER, quantity REAL DEFAULT 0, reason TEXT, disposition TEXT, operator INTEGER, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_routing_card (
        id SERIAL PRIMARY KEY,
        card_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        product_id INTEGER,
        current_step INTEGER DEFAULT 1,
        total_steps INTEGER DEFAULT 1,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_routing_card_step (
        id SERIAL PRIMARY KEY,
        card_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        process_name TEXT,
        station TEXT,
        operator INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        result TEXT);
CREATE TABLE IF NOT EXISTS prod_sales_order (
        id SERIAL PRIMARY KEY,
        order_no TEXT NOT NULL UNIQUE,
        customer TEXT NOT NULL,
        contact TEXT,
        phone TEXT,
        total_amount REAL DEFAULT 0,
        delivery_date TEXT,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , "customer_id" INTEGER);
CREATE TABLE IF NOT EXISTS prod_sales_order_item (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        delivered_qty REAL DEFAULT 0,
        remark TEXT);
CREATE TABLE IF NOT EXISTS prod_serial (
        id SERIAL PRIMARY KEY,
        serial_no TEXT NOT NULL UNIQUE,
        product_id INTEGER NOT NULL,
        workorder_id INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "quality_status" TEXT NOT NULL DEFAULT 'normal');
CREATE TABLE IF NOT EXISTS prod_stage_record (
            id SERIAL PRIMARY KEY, stage_code TEXT,
            workorder_id INTEGER, product_id INTEGER, quantity REAL DEFAULT 0,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, end_time TIMESTAMP,
            duration REAL DEFAULT 0, operator INTEGER, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS prod_station_flow (
        id SERIAL PRIMARY KEY,
        flow_no TEXT NOT NULL UNIQUE,
        sn TEXT,
        product_id INTEGER,
        workorder_id INTEGER,
        current_station TEXT,
        current_process TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS prod_station_record (
        id SERIAL PRIMARY KEY,
        flow_id INTEGER NOT NULL,
        sn TEXT,
        station TEXT NOT NULL,
        process_name TEXT,
        action TEXT NOT NULL,
        operator INTEGER,
        result TEXT,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "route_step_id" INTEGER, "machine_request_id" INTEGER, "quality_disposition_id" INTEGER);
CREATE TABLE IF NOT EXISTS prod_task (
        id SERIAL PRIMARY KEY,
        task_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        assigned_to INTEGER,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        defect_qty REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "route_step_id" INTEGER, "task_type" TEXT NOT NULL DEFAULT 'normal', "source_task_id" INTEGER, "quality_disposition_id" INTEGER, "target_sn" TEXT);
CREATE TABLE IF NOT EXISTS prod_transfer (
        id SERIAL PRIMARY KEY,
        transfer_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        from_process_id INTEGER NOT NULL,
        to_process_id INTEGER NOT NULL,
        from_route_step_id INTEGER,
        to_route_step_id INTEGER,
        quantity REAL NOT NULL,
        status INTEGER DEFAULT 1,
        operator INTEGER,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_workorder (
        id SERIAL PRIMARY KEY,
        order_no TEXT NOT NULL UNIQUE,
        plan_id INTEGER,
        sales_order_id INTEGER,
        product_id INTEGER NOT NULL,
        route_id INTEGER,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        defect_qty REAL DEFAULT 0,
        workshop_id INTEGER,
        priority INTEGER DEFAULT 1,
        status INTEGER DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "plan_item_id" INTEGER, "production_batch_id" INTEGER, "route_version" INTEGER, "bom_version" TEXT);
CREATE TABLE IF NOT EXISTS prod_workorder_bom_snapshot (
        id SERIAL PRIMARY KEY,
        workorder_id INTEGER NOT NULL,
        source_bom_id INTEGER,
        material_id INTEGER NOT NULL,
        material_code TEXT,
        material_name TEXT NOT NULL,
        quantity_per_unit REAL NOT NULL,
        required_qty REAL NOT NULL,
        unit TEXT,
        bom_version TEXT,
        frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(workorder_id, material_id));
CREATE TABLE IF NOT EXISTS prod_workorder_route_snapshot (
        id SERIAL PRIMARY KEY,
        workorder_id INTEGER NOT NULL UNIQUE,
        source_route_id INTEGER,
        route_name TEXT NOT NULL,
        route_version INTEGER DEFAULT 1,
        product_id INTEGER NOT NULL,
        workshop_id INTEGER NOT NULL,
        description TEXT,
        frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS prod_workorder_route_step (
        id SERIAL PRIMARY KEY,
        snapshot_id INTEGER NOT NULL,
        source_detail_id INTEGER,
        process_id INTEGER NOT NULL,
        process_code TEXT,
        process_name TEXT NOT NULL,
        workshop_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        standard_time REAL,
        is_inspection_point INTEGER DEFAULT 0,
        description TEXT,
        UNIQUE(snapshot_id, step_no));
CREATE TABLE IF NOT EXISTS qm_8d_report (id SERIAL PRIMARY KEY, report_no TEXT UNIQUE, title TEXT, customer TEXT, problem TEXT, root_cause TEXT, corrective_action TEXT, owner TEXT, due_date TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qm_capa (id SERIAL PRIMARY KEY, capa_no TEXT UNIQUE, source TEXT, issue TEXT, root_cause TEXT, corrective_action TEXT, preventive_action TEXT, owner TEXT, due_date TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qm_control_plan (id SERIAL PRIMARY KEY, plan_no TEXT UNIQUE, product_id INTEGER, process_id INTEGER, control_item TEXT, specification TEXT, method TEXT, frequency TEXT, reaction_plan TEXT, status INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qm_defect_process (id SERIAL PRIMARY KEY, defect_no TEXT UNIQUE, workorder_id INTEGER, defect_id INTEGER, quantity REAL DEFAULT 0, disposition TEXT, responsible TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qm_eco (id SERIAL PRIMARY KEY, eco_no TEXT UNIQUE, title TEXT, change_reason TEXT, change_content TEXT, applicant INTEGER, effective_date TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qm_first_inspect (id SERIAL PRIMARY KEY, inspect_no TEXT UNIQUE, workorder_id INTEGER, process_id INTEGER, inspector INTEGER, result TEXT, inspect_date TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qm_fmea (
        id SERIAL PRIMARY KEY,
        fmea_no TEXT NOT NULL UNIQUE,
        product_id INTEGER,
        process_id INTEGER,
        failure_mode TEXT,
        failure_effect TEXT,
        failure_cause TEXT,
        severity INTEGER DEFAULT 1,
        occurrence INTEGER DEFAULT 1,
        detection INTEGER DEFAULT 1,
        rpn INTEGER DEFAULT 1,
        current_control TEXT,
        recommended_action TEXT,
        responsible TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS qm_incoming_inspection (
        id SERIAL PRIMARY KEY,
        inspect_no TEXT NOT NULL UNIQUE,
        inbound_id INTEGER,
        supplier TEXT,
        template_id INTEGER,
        result TEXT,
        status INTEGER DEFAULT 0,
        inspector INTEGER,
        inspect_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , "inspection_no" TEXT, "arrival_item_id" INTEGER, "mode" TEXT, "sampled_qty" REAL, "passed_qty" REAL, "failed_qty" REAL, "pending_qty" REAL, "conclusion" TEXT, "inspector_id" INTEGER, "inspected_at" TIMESTAMP, "concession_approved_by" INTEGER, "concession_reason" TEXT);
CREATE TABLE IF NOT EXISTS qm_incoming_inspection_item (
            id SERIAL PRIMARY KEY,
            inspection_id INTEGER NOT NULL,
            item_name TEXT,
            standard TEXT,
            measured_value TEXT,
            result TEXT,
            defect_id INTEGER,
            defect_qty REAL DEFAULT 0,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qm_inspect_template (
        id SERIAL PRIMARY KEY,
        template_name TEXT NOT NULL,
        inspect_type TEXT NOT NULL,
        items TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS qm_inspection_item (
        id SERIAL PRIMARY KEY,
        item_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        standard TEXT,
        method TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS qm_inspection_template (
        id SERIAL PRIMARY KEY,
        template_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        inspection_type TEXT,
        item_ids TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS qm_outgoing_inspection (
        id SERIAL PRIMARY KEY,
        inspect_no TEXT NOT NULL UNIQUE,
        outbound_id INTEGER,
        customer TEXT,
        template_id INTEGER,
        result TEXT,
        status INTEGER DEFAULT 0,
        inspector INTEGER,
        inspect_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS qm_process_inspection (
        id SERIAL PRIMARY KEY,
        inspect_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER,
        task_id INTEGER,
        template_id INTEGER,
        result TEXT,
        status INTEGER DEFAULT 0,
        inspector INTEGER,
        inspect_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS qm_supplier_eval (id SERIAL PRIMARY KEY, supplier_id INTEGER, eval_date TEXT, quality_score REAL DEFAULT 0, delivery_score REAL DEFAULT 0, service_score REAL DEFAULT 0, total_score REAL DEFAULT 0, grade TEXT, evaluator INTEGER, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sched_calendar (
        id SERIAL PRIMARY KEY,
        plan_id INTEGER NOT NULL,
        work_date TEXT NOT NULL,
        shift_type TEXT,
        user_ids TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sched_holiday (
        id SERIAL PRIMARY KEY,
        holiday_name TEXT NOT NULL,
        holiday_date TEXT NOT NULL,
        holiday_type TEXT,
        is_workday INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sched_plan (
        id SERIAL PRIMARY KEY,
        plan_name TEXT NOT NULL,
        team_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        shift_type TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sched_team (
        id SERIAL PRIMARY KEY,
        team_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        leader TEXT,
        member_count INTEGER DEFAULT 0,
        workshop_id INTEGER,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS scm_procurement_status_log (
            id SERIAL PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT,
            action TEXT NOT NULL,
            operator_id INTEGER NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS scm_purchase_order (
            id SERIAL PRIMARY KEY,
            order_no TEXT NOT NULL UNIQUE,
            supplier_id INTEGER NOT NULL,
            status INTEGER NOT NULL DEFAULT 0,
            expected_date TEXT,
            currency TEXT,
            remark TEXT,
            created_by INTEGER NOT NULL,
            submitted_by INTEGER,
            submitted_at TIMESTAMP,
            approved_by INTEGER,
            approved_at TIMESTAMP,
            rejected_reason TEXT,
            closed_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS scm_purchase_order_item (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            ordered_qty REAL NOT NULL,
            unit_price REAL DEFAULT 0,
            tax_rate REAL DEFAULT 0,
            arrived_qty REAL DEFAULT 0,
            accepted_qty REAL DEFAULT 0,
            returned_qty REAL DEFAULT 0,
            posted_qty REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS spc_data (id SERIAL PRIMARY KEY, equipment_id INTEGER, process_id INTEGER, item_name TEXT, value REAL, unit TEXT, collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sqlite_sequence (name,seq);
CREATE TABLE IF NOT EXISTS svc_complaint (id SERIAL PRIMARY KEY, complaint_no TEXT UNIQUE, customer_id INTEGER, product_id INTEGER, complaint_type TEXT, severity TEXT DEFAULT 'medium', description TEXT, complaint_date TEXT, handler INTEGER, resolution TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS svc_return (id SERIAL PRIMARY KEY, return_no TEXT UNIQUE, complaint_id INTEGER, customer_id INTEGER, product_id INTEGER, quantity REAL DEFAULT 0, return_reason TEXT, return_date TEXT, handler INTEGER, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sys_5s_audit (
            id SERIAL PRIMARY KEY, audit_no TEXT UNIQUE,
            workshop_id INTEGER, auditor INTEGER, audit_date TEXT,
            sort_score INTEGER DEFAULT 0, set_in_order_score INTEGER DEFAULT 0,
            shine_score INTEGER DEFAULT 0, standardize_score INTEGER DEFAULT 0,
            sustain_score INTEGER DEFAULT 0, total_score REAL DEFAULT 0,
            issues TEXT, corrective_action TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS sys_announcement (id SERIAL PRIMARY KEY, title TEXT, content TEXT, announcement_type TEXT, publisher INTEGER, publish_time TEXT, expire_time TEXT, priority INTEGER DEFAULT 0, status INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sys_backup (
            id SERIAL PRIMARY KEY, backup_name TEXT NOT NULL,
            file_path TEXT, file_size INTEGER, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS sys_barcode (id SERIAL PRIMARY KEY, barcode TEXT UNIQUE, biz_type TEXT, biz_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sys_business_status_log (
        id SERIAL PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        from_status INTEGER,
        to_status INTEGER NOT NULL,
        action TEXT,
        operator_id INTEGER,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_config (
        id SERIAL PRIMARY KEY,
        config_key TEXT NOT NULL UNIQUE,
        config_value TEXT,
        config_type TEXT DEFAULT 'string',
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_dept (
        id SERIAL PRIMARY KEY,
        dept_name TEXT NOT NULL,
        parent_id INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        leader TEXT,
        phone TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_dict (
        id SERIAL PRIMARY KEY,
        dict_type TEXT NOT NULL,
        dict_label TEXT NOT NULL,
        dict_value TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        status INTEGER DEFAULT 1
    );
CREATE TABLE IF NOT EXISTS sys_document (
            id SERIAL PRIMARY KEY, doc_name TEXT NOT NULL,
            doc_type TEXT, category TEXT, file_path TEXT, file_size INTEGER,
            uploader INTEGER, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        , "version" TEXT DEFAULT '1.0');
CREATE TABLE IF NOT EXISTS sys_ip_whitelist (
        id SERIAL PRIMARY KEY,
        ip_address TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        username TEXT,
        operation TEXT,
        method TEXT,
        url TEXT,
        ip TEXT,
        params TEXT,
        result TEXT,
        cost_time INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_login_log (
        id SERIAL PRIMARY KEY,
        username TEXT,
        login_ip TEXT,
        status INTEGER DEFAULT 1,
        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_menu (
        id SERIAL PRIMARY KEY,
        menu_name TEXT NOT NULL,
        parent_id INTEGER DEFAULT 0,
        path TEXT,
        component TEXT,
        icon TEXT,
        sort_order INTEGER DEFAULT 0,
        menu_type TEXT DEFAULT 'M',
        perms TEXT,
        status INTEGER DEFAULT 1
    );
CREATE TABLE IF NOT EXISTS sys_notice (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT,
        notice_type TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_notification (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        link TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sys_notify_channel (
        id SERIAL PRIMARY KEY,
        channel_name TEXT NOT NULL,
        channel_type TEXT NOT NULL,
        config TEXT,
        enabled INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_numbering (
        id SERIAL PRIMARY KEY,
        prefix TEXT NOT NULL,
        entity_type TEXT NOT NULL UNIQUE,
        current_no INTEGER DEFAULT 0,
        digit_count INTEGER DEFAULT 6,
        description TEXT
    );
CREATE TABLE IF NOT EXISTS sys_print_template (
        id SERIAL PRIMARY KEY,
        template_name TEXT NOT NULL,
        biz_type TEXT,
        template_content TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_role (
        id SERIAL PRIMARY KEY,
        role_name TEXT NOT NULL,
        role_key TEXT NOT NULL UNIQUE,
        description TEXT,
        menu_ids TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_table_order (
        id SERIAL PRIMARY KEY,
        table_key TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        position INTEGER NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(table_key, record_id)
    );
CREATE TABLE IF NOT EXISTS sys_tenant (
        id SERIAL PRIMARY KEY,
        tenant_name TEXT NOT NULL,
        tenant_code TEXT NOT NULL UNIQUE,
        contact TEXT,
        phone TEXT,
        max_users INTEGER DEFAULT 100,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_user (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        real_name TEXT,
        phone TEXT,
        email TEXT,
        dept_id INTEGER,
        role_id INTEGER,
        tenant_id INTEGER DEFAULT 1,
        status INTEGER DEFAULT 1,
        avatar TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS sys_version (
        id SERIAL PRIMARY KEY,
        version_no TEXT NOT NULL,
        release_date TEXT,
        changes TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS tool_borrow (
        id SERIAL PRIMARY KEY,
        borrow_no TEXT NOT NULL UNIQUE,
        tool_id INTEGER NOT NULL,
        borrower INTEGER NOT NULL,
        borrow_qty REAL NOT NULL,
        borrow_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        return_time TIMESTAMP,
        return_qty REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        remark TEXT);
CREATE TABLE IF NOT EXISTS tool_ledger (
        id SERIAL PRIMARY KEY,
        tool_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        type_id INTEGER,
        specification TEXT,
        quantity REAL DEFAULT 0,
        location TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS tool_type (
        id SERIAL PRIMARY KEY,
        type_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1
    );
CREATE TABLE IF NOT EXISTS util_energy (
            id SERIAL PRIMARY KEY, workshop_id INTEGER,
            energy_type TEXT, quantity REAL DEFAULT 0, unit TEXT,
            cost REAL DEFAULT 0, record_date TEXT, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS util_environment (
            id SERIAL PRIMARY KEY, workshop_id INTEGER,
            temperature REAL, humidity REAL, noise REAL, pm25 REAL,
            voc REAL, recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE INDEX idx_arrival_item_notice ON inv_arrival_notice_item(notice_id);
CREATE INDEX idx_arrival_purchase_order ON inv_arrival_notice(purchase_order_id);
CREATE INDEX idx_business_status_entity ON sys_business_status_log(entity_type, entity_id);
CREATE UNIQUE INDEX idx_flow_active_business
                      ON flow_instance(biz_type, biz_id)
                      WHERE status=0 AND biz_type IS NOT NULL AND biz_type<>'';
CREATE UNIQUE INDEX idx_flow_task_instance_step
                      ON flow_task(instance_id, step_no);
CREATE INDEX idx_gateway_nonce_expiry ON iot_gateway_nonce(expires_at);
CREATE INDEX idx_inspection_arrival_item ON qm_incoming_inspection(arrival_item_id);
CREATE INDEX idx_inv_balance_product ON inv_balance(product_id);
CREATE INDEX idx_iot_command_queue ON iot_device_command(gateway_code,device_code,status,created_at);
CREATE INDEX idx_iot_device_event_identity_sequence ON iot_device_event(factory_code,device_code,lifecycle_id,sequence);
CREATE UNIQUE INDEX idx_iot_device_event_identity_sequence_uq
            ON iot_device_event(factory_code,device_code,lifecycle_id,sequence);
CREATE INDEX idx_iot_device_event_status ON iot_device_event(processing_status,ingested_at);
CREATE INDEX idx_iot_device_gap_status ON iot_device_sequence_gap(status,factory_code,device_code);
CREATE INDEX idx_iot_event_processing_queue ON iot_device_event(processing_status,next_processing_at,ingested_at);
CREATE UNIQUE INDEX idx_iot_inspection_report_hash ON iot_inspection_report(endpoint_id,file_hash);
CREATE INDEX idx_iot_inspection_value_report ON iot_inspection_value(report_id);
CREATE UNIQUE INDEX idx_iot_machine_endpoint_binding ON iot_machine_endpoint(bind_ip,listen_port,station_code,cavity_code);
CREATE UNIQUE INDEX idx_iot_machine_pending_step
           ON iot_machine_request(endpoint_id,sn,route_step_id)
           WHERE decision='L1' AND report_status='pending';
CREATE UNIQUE INDEX idx_iot_machine_request_dedupe ON iot_machine_request(dedupe_key);
CREATE INDEX idx_iot_machine_request_sn ON iot_machine_request(sn,requested_at);
CREATE INDEX idx_iot_machine_session_endpoint ON iot_machine_session(endpoint_id,status);
CREATE INDEX idx_plan_item_plan ON prod_plan_item(plan_id);
CREATE INDEX idx_procurement_status_entity ON scm_procurement_status_log(entity_type, entity_id);
CREATE INDEX idx_prod_batch_plan_item ON prod_batch(plan_item_id);
CREATE INDEX idx_prod_batch_product ON prod_batch(product_id);
CREATE INDEX idx_prod_bom_snapshot_workorder ON prod_workorder_bom_snapshot(workorder_id);
CREATE INDEX idx_prod_material_snapshot ON prod_material_req(bom_snapshot_id);
CREATE INDEX idx_prod_material_workorder ON prod_material_req(workorder_id);
CREATE INDEX idx_prod_report_task ON prod_report(task_id);
CREATE INDEX idx_prod_report_time ON prod_report(report_time);
CREATE UNIQUE INDEX idx_prod_report_user_operation
           ON prod_report(user_id, client_operation_id)
           WHERE client_operation_id IS NOT NULL;
CREATE INDEX idx_prod_route_step_process ON prod_workorder_route_step(process_id);
CREATE INDEX idx_prod_route_step_snapshot ON prod_workorder_route_step(snapshot_id);
CREATE INDEX idx_prod_station_flow_sn ON prod_station_flow(sn);
CREATE INDEX idx_prod_station_record_sn ON prod_station_record(sn);
CREATE INDEX idx_prod_task_status ON prod_task(status);
CREATE INDEX idx_prod_task_workorder ON prod_task(workorder_id);
CREATE INDEX idx_prod_workorder_status ON prod_workorder(status);
CREATE INDEX idx_purchase_item_order ON scm_purchase_order_item(order_id);
CREATE INDEX idx_purchase_order_supplier ON scm_purchase_order(supplier_id);
CREATE UNIQUE INDEX idx_quality_disposition_open_sn_step
           ON prod_quality_disposition(sn, route_step_id)
           WHERE status IN ('pending_review','approved','task_started');
CREATE INDEX idx_quality_disposition_source_task
           ON prod_quality_disposition(source_task_id, status);
CREATE INDEX idx_route_detail_route ON base_process_route_detail(route_id);
CREATE INDEX idx_sales_item_order ON prod_sales_order_item(order_id);
CREATE UNIQUE INDEX idx_station_record_disposition
           ON prod_station_record(quality_disposition_id)
           WHERE quality_disposition_id IS NOT NULL;
CREATE INDEX idx_sys_log_time ON sys_log(created_at);
CREATE INDEX idx_sys_notification_user ON sys_notification(user_id, is_read);
CREATE INDEX idx_sys_table_order_position
                  ON sys_table_order(table_key, position);
CREATE UNIQUE INDEX uq_inv_receipt_action_operation
       ON inv_receipt_action(operator_id, client_operation_id)
       WHERE client_operation_id IS NOT NULL;
CREATE UNIQUE INDEX uq_inv_receipt_posting_operation
       ON inv_receipt_posting(operator_id, client_operation_id)
       WHERE client_operation_id IS NOT NULL;
CREATE UNIQUE INDEX uq_inv_stock_balance_identity
       ON inv_stock_balance(product_id, warehouse_id, area_id, location_id, batch_no);
CREATE UNIQUE INDEX uq_qm_incoming_inspection_no
       ON qm_incoming_inspection(inspection_no)
       WHERE inspection_no IS NOT NULL;
ALTER TABLE base_bom ADD CONSTRAINT base_bom_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE base_bom ADD CONSTRAINT base_bom_material_id_fk FOREIGN KEY (material_id) REFERENCES base_product(id);
ALTER TABLE base_process ADD CONSTRAINT base_process_workshop_id_fk FOREIGN KEY (workshop_id) REFERENCES base_workshop(id);
ALTER TABLE base_process_route ADD CONSTRAINT base_process_route_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE base_process_route_detail ADD CONSTRAINT base_process_route_detail_route_id_fk FOREIGN KEY (route_id) REFERENCES base_process_route(id);
ALTER TABLE base_process_route_detail ADD CONSTRAINT base_process_route_detail_process_id_fk FOREIGN KEY (process_id) REFERENCES base_process(id);
ALTER TABLE base_salary_config ADD CONSTRAINT base_salary_config_process_id_fk FOREIGN KEY (process_id) REFERENCES base_process(id);
ALTER TABLE base_standard_cost ADD CONSTRAINT base_standard_cost_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE eqp_check_workorder ADD CONSTRAINT eqp_check_workorder_plan_id_fk FOREIGN KEY (plan_id) REFERENCES eqp_maintenance_plan(id);
ALTER TABLE eqp_check_workorder ADD CONSTRAINT eqp_check_workorder_equipment_id_fk FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id);
ALTER TABLE eqp_ledger ADD CONSTRAINT eqp_ledger_type_id_fk FOREIGN KEY (type_id) REFERENCES eqp_type(id);
ALTER TABLE eqp_maintenance_plan ADD CONSTRAINT eqp_maintenance_plan_equipment_id_fk FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id);
ALTER TABLE eqp_repair_order ADD CONSTRAINT eqp_repair_order_equipment_id_fk FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id);
ALTER TABLE flow_instance ADD CONSTRAINT flow_instance_flow_id_fk FOREIGN KEY (flow_id) REFERENCES flow_definition(id);
ALTER TABLE flow_task ADD CONSTRAINT flow_task_instance_id_fk FOREIGN KEY (instance_id) REFERENCES flow_instance(id);
ALTER TABLE inv_area ADD CONSTRAINT inv_area_warehouse_id_fk FOREIGN KEY (warehouse_id) REFERENCES inv_warehouse(id);
ALTER TABLE inv_arrival_notice_item ADD CONSTRAINT inv_arrival_notice_item_notice_id_fk FOREIGN KEY (notice_id) REFERENCES inv_arrival_notice(id);
ALTER TABLE inv_balance ADD CONSTRAINT inv_balance_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE inv_inbound_item ADD CONSTRAINT inv_inbound_item_inbound_id_fk FOREIGN KEY (inbound_id) REFERENCES inv_inbound(id);
ALTER TABLE inv_inbound_item ADD CONSTRAINT inv_inbound_item_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE inv_line_warehouse ADD CONSTRAINT inv_line_warehouse_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE inv_location ADD CONSTRAINT inv_location_area_id_fk FOREIGN KEY (area_id) REFERENCES inv_area(id);
ALTER TABLE inv_outbound_item ADD CONSTRAINT inv_outbound_item_outbound_id_fk FOREIGN KEY (outbound_id) REFERENCES inv_outbound(id);
ALTER TABLE inv_outbound_item ADD CONSTRAINT inv_outbound_item_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE inv_receipt_action ADD CONSTRAINT inv_receipt_action_arrival_item_id_fk FOREIGN KEY (arrival_item_id) REFERENCES inv_arrival_notice_item(id);
ALTER TABLE inv_receipt_posting ADD CONSTRAINT inv_receipt_posting_arrival_item_id_fk FOREIGN KEY (arrival_item_id) REFERENCES inv_arrival_notice_item(id);
ALTER TABLE inv_receipt_posting ADD CONSTRAINT inv_receipt_posting_inspection_id_fk FOREIGN KEY (inspection_id) REFERENCES qm_incoming_inspection(id);
ALTER TABLE inv_receipt_posting ADD CONSTRAINT inv_receipt_posting_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE inv_receipt_posting ADD CONSTRAINT inv_receipt_posting_warehouse_id_fk FOREIGN KEY (warehouse_id) REFERENCES inv_warehouse(id);
ALTER TABLE inv_receipt_posting ADD CONSTRAINT inv_receipt_posting_area_id_fk FOREIGN KEY (area_id) REFERENCES inv_area(id);
ALTER TABLE inv_receipt_posting ADD CONSTRAINT inv_receipt_posting_location_id_fk FOREIGN KEY (location_id) REFERENCES inv_location(id);
ALTER TABLE inv_stock_balance ADD CONSTRAINT inv_stock_balance_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE inv_stock_balance ADD CONSTRAINT inv_stock_balance_warehouse_id_fk FOREIGN KEY (warehouse_id) REFERENCES inv_warehouse(id);
ALTER TABLE inv_stock_balance ADD CONSTRAINT inv_stock_balance_area_id_fk FOREIGN KEY (area_id) REFERENCES inv_area(id);
ALTER TABLE inv_stock_balance ADD CONSTRAINT inv_stock_balance_location_id_fk FOREIGN KEY (location_id) REFERENCES inv_location(id);
ALTER TABLE inv_transaction ADD CONSTRAINT inv_transaction_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE iot_inspection_report ADD CONSTRAINT iot_inspection_report_request_id_fk FOREIGN KEY (request_id) REFERENCES iot_machine_request(id);
ALTER TABLE iot_inspection_report ADD CONSTRAINT iot_inspection_report_endpoint_id_fk FOREIGN KEY (endpoint_id) REFERENCES iot_machine_endpoint(id);
ALTER TABLE iot_inspection_report ADD CONSTRAINT iot_inspection_report_prod_report_id_fk FOREIGN KEY (prod_report_id) REFERENCES prod_report(id);
ALTER TABLE iot_inspection_value ADD CONSTRAINT iot_inspection_value_report_id_fk FOREIGN KEY (report_id) REFERENCES iot_inspection_report(id);
ALTER TABLE iot_machine_endpoint ADD CONSTRAINT iot_machine_endpoint_equipment_id_fk FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id);
ALTER TABLE iot_machine_endpoint ADD CONSTRAINT iot_machine_endpoint_process_id_fk FOREIGN KEY (process_id) REFERENCES base_process(id);
ALTER TABLE iot_machine_request ADD CONSTRAINT iot_machine_request_endpoint_id_fk FOREIGN KEY (endpoint_id) REFERENCES iot_machine_endpoint(id);
ALTER TABLE iot_machine_request ADD CONSTRAINT iot_machine_request_session_id_fk FOREIGN KEY (session_id) REFERENCES iot_machine_session(id);
ALTER TABLE iot_machine_request ADD CONSTRAINT iot_machine_request_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE iot_machine_request ADD CONSTRAINT iot_machine_request_task_id_fk FOREIGN KEY (task_id) REFERENCES prod_task(id);
ALTER TABLE iot_machine_session ADD CONSTRAINT iot_machine_session_endpoint_id_fk FOREIGN KEY (endpoint_id) REFERENCES iot_machine_endpoint(id);
ALTER TABLE job_log ADD CONSTRAINT job_log_job_id_fk FOREIGN KEY (job_id) REFERENCES job_config(id);
ALTER TABLE prod_batch ADD CONSTRAINT prod_batch_plan_item_id_fk FOREIGN KEY (plan_item_id) REFERENCES prod_plan_item(id);
ALTER TABLE prod_batch ADD CONSTRAINT prod_batch_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE prod_batch ADD CONSTRAINT prod_batch_workshop_id_fk FOREIGN KEY (workshop_id) REFERENCES base_workshop(id);
ALTER TABLE prod_plan_item ADD CONSTRAINT prod_plan_item_plan_id_fk FOREIGN KEY (plan_id) REFERENCES prod_plan(id);
ALTER TABLE prod_plan_item ADD CONSTRAINT prod_plan_item_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE prod_quality_disposition ADD CONSTRAINT prod_quality_disposition_inspection_report_id_fk FOREIGN KEY (inspection_report_id) REFERENCES iot_inspection_report(id);
ALTER TABLE prod_quality_disposition ADD CONSTRAINT prod_quality_disposition_machine_request_id_fk FOREIGN KEY (machine_request_id) REFERENCES iot_machine_request(id);
ALTER TABLE prod_quality_disposition ADD CONSTRAINT prod_quality_disposition_prod_report_id_fk FOREIGN KEY (prod_report_id) REFERENCES prod_report(id);
ALTER TABLE prod_quality_disposition ADD CONSTRAINT prod_quality_disposition_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_quality_disposition ADD CONSTRAINT prod_quality_disposition_source_task_id_fk FOREIGN KEY (source_task_id) REFERENCES prod_task(id);
ALTER TABLE prod_quality_disposition ADD CONSTRAINT prod_quality_disposition_route_step_id_fk FOREIGN KEY (route_step_id) REFERENCES prod_workorder_route_step(id);
ALTER TABLE prod_quality_disposition ADD CONSTRAINT prod_quality_disposition_rework_task_id_fk FOREIGN KEY (rework_task_id) REFERENCES prod_task(id);
ALTER TABLE prod_report ADD CONSTRAINT prod_report_task_id_fk FOREIGN KEY (task_id) REFERENCES prod_task(id);
ALTER TABLE prod_report ADD CONSTRAINT prod_report_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_routing_card ADD CONSTRAINT prod_routing_card_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_routing_card_step ADD CONSTRAINT prod_routing_card_step_card_id_fk FOREIGN KEY (card_id) REFERENCES prod_routing_card(id);
ALTER TABLE prod_sales_order_item ADD CONSTRAINT prod_sales_order_item_order_id_fk FOREIGN KEY (order_id) REFERENCES prod_sales_order(id);
ALTER TABLE prod_sales_order_item ADD CONSTRAINT prod_sales_order_item_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE prod_serial ADD CONSTRAINT prod_serial_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE prod_serial ADD CONSTRAINT prod_serial_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_station_record ADD CONSTRAINT prod_station_record_flow_id_fk FOREIGN KEY (flow_id) REFERENCES prod_station_flow(id);
ALTER TABLE prod_task ADD CONSTRAINT prod_task_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_task ADD CONSTRAINT prod_task_process_id_fk FOREIGN KEY (process_id) REFERENCES base_process(id);
ALTER TABLE prod_transfer ADD CONSTRAINT prod_transfer_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_workorder ADD CONSTRAINT prod_workorder_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE prod_workorder_bom_snapshot ADD CONSTRAINT prod_workorder_bom_snapshot_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_workorder_bom_snapshot ADD CONSTRAINT prod_workorder_bom_snapshot_material_id_fk FOREIGN KEY (material_id) REFERENCES base_product(id);
ALTER TABLE prod_workorder_route_snapshot ADD CONSTRAINT prod_workorder_route_snapshot_workorder_id_fk FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id);
ALTER TABLE prod_workorder_route_step ADD CONSTRAINT prod_workorder_route_step_snapshot_id_fk FOREIGN KEY (snapshot_id) REFERENCES prod_workorder_route_snapshot(id);
ALTER TABLE prod_workorder_route_step ADD CONSTRAINT prod_workorder_route_step_process_id_fk FOREIGN KEY (process_id) REFERENCES base_process(id);
ALTER TABLE qm_incoming_inspection_item ADD CONSTRAINT qm_incoming_inspection_item_inspection_id_fk FOREIGN KEY (inspection_id) REFERENCES qm_incoming_inspection(id);
ALTER TABLE sched_calendar ADD CONSTRAINT sched_calendar_plan_id_fk FOREIGN KEY (plan_id) REFERENCES sched_plan(id);
ALTER TABLE sched_plan ADD CONSTRAINT sched_plan_team_id_fk FOREIGN KEY (team_id) REFERENCES sched_team(id);
ALTER TABLE scm_purchase_order ADD CONSTRAINT scm_purchase_order_supplier_id_fk FOREIGN KEY (supplier_id) REFERENCES base_supplier(id);
ALTER TABLE scm_purchase_order_item ADD CONSTRAINT scm_purchase_order_item_order_id_fk FOREIGN KEY (order_id) REFERENCES scm_purchase_order(id);
ALTER TABLE scm_purchase_order_item ADD CONSTRAINT scm_purchase_order_item_product_id_fk FOREIGN KEY (product_id) REFERENCES base_product(id);
ALTER TABLE sys_notification ADD CONSTRAINT sys_notification_user_id_fk FOREIGN KEY (user_id) REFERENCES sys_user(id);
ALTER TABLE tool_borrow ADD CONSTRAINT tool_borrow_tool_id_fk FOREIGN KEY (tool_id) REFERENCES tool_ledger(id);
ALTER TABLE tool_ledger ADD CONSTRAINT tool_ledger_type_id_fk FOREIGN KEY (type_id) REFERENCES tool_type(id);
COMMIT;
