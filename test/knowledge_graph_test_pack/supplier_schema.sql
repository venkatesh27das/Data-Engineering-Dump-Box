-- Synthetic procurement schema for Knowledge Graph Builder POC
-- No real company or client data.

CREATE TABLE suppliers (
    supplier_id VARCHAR(20) PRIMARY KEY,
    supplier_name VARCHAR(200) NOT NULL,
    supplier_alias VARCHAR(200),
    supplier_tier VARCHAR(20),
    country VARCHAR(100),
    status VARCHAR(30)
);

CREATE TABLE products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    product_category VARCHAR(100),
    preferred_supplier_id VARCHAR(20),
    unit_of_measure VARCHAR(30),
    FOREIGN KEY (preferred_supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE contracts (
    contract_id VARCHAR(30) PRIMARY KEY,
    contract_name VARCHAR(250) NOT NULL,
    supplier_id VARCHAR(20) NOT NULL,
    effective_date DATE,
    expiry_date DATE,
    currency VARCHAR(10),
    contract_status VARCHAR(30),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE contract_products (
    contract_id VARCHAR(30),
    product_id VARCHAR(20),
    agreed_unit_price DECIMAL(12,2),
    minimum_order_qty INTEGER,
    PRIMARY KEY (contract_id, product_id),
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE obligations (
    obligation_id VARCHAR(30) PRIMARY KEY,
    contract_id VARCHAR(30) NOT NULL,
    obligation_type VARCHAR(80),
    obligation_text VARCHAR(500),
    due_day INTEGER,
    severity VARCHAR(20),
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id)
);
