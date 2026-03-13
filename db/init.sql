-- ============================================
-- Database Initialization Script
-- Executed ONLY on first boot (empty data directory)
-- Creates all 9 service databases with schemas and seed data
-- ============================================

-- ============================================
-- 1. Event Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS event_db;
USE event_db;

CREATE TABLE IF NOT EXISTS events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    event_date DATETIME NOT NULL,
    venue VARCHAR(255),
    status ENUM('upcoming', 'ongoing', 'completed', 'cancelled') DEFAULT 'upcoming',
    total_seats INT NOT NULL,
    available_seats INT NOT NULL,
    price_min DECIMAL(10, 2),
    price_max DECIMAL(10, 2),
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_category (category),
    INDEX idx_event_date (event_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 2. Booking Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS booking_db;
USE booking_db;

CREATE TABLE IF NOT EXISTS bookings (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    event_id INT NOT NULL,
    seat_id INT NOT NULL,
    email VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status ENUM('pending', 'confirmed', 'cancelled', 'failed', 'expired', 'pending_refund', 'refunded') DEFAULT 'pending',
    payment_intent_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_event_id (event_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 3. Seat Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS seat_db;
USE seat_db;

CREATE TABLE IF NOT EXISTS sections (
    section_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    total_seats INT NOT NULL,
    available_seats INT NOT NULL,
    INDEX idx_event_id (event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS seats (
    seat_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    section_id INT NOT NULL,
    seat_number VARCHAR(20) NOT NULL,
    status ENUM('available', 'reserved', 'booked') DEFAULT 'available',
    reserved_by VARCHAR(100),
    reserved_at TIMESTAMP NULL,
    UNIQUE KEY uk_event_seat (event_id, seat_number),
    INDEX idx_event_section (event_id, section_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 4. Payment Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS payment_db;
USE payment_db;

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'SGD',
    stripe_payment_intent_id VARCHAR(255),
    status ENUM('pending', 'succeeded', 'failed', 'refunded') DEFAULT 'pending',
    refund_amount DECIMAL(10, 2) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_booking_id (booking_id),
    INDEX idx_stripe_pi (stripe_payment_intent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 5. Notification Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS notification_db;
USE notification_db;

CREATE TABLE IF NOT EXISTS notification_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    channel ENUM('email', 'sms') NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    subject VARCHAR(255),
    body TEXT,
    status ENUM('sent', 'failed', 'pending') DEFAULT 'pending',
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 6. Ticket Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS ticket_db;
USE ticket_db;

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,
    event_id INT NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    seat_id INT NOT NULL,
    qr_code_data TEXT NOT NULL,
    qr_code_image LONGBLOB,
    status ENUM('valid', 'used', 'invalidated') DEFAULT 'valid',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_booking_id (booking_id),
    INDEX idx_event_id (event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 7. Waitlist Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS waitlist_db;
USE waitlist_db;

CREATE TABLE IF NOT EXISTS waitlist_entries (
    entry_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    preferred_section VARCHAR(100),
    position INT NOT NULL,
    status ENUM('waiting', 'promoted', 'expired', 'cancelled', 'booked') DEFAULT 'waiting',
    promoted_seat_id INT NULL,
    promotion_expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_event_status (event_id, status),
    INDEX idx_user_event (user_id, event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 8. Charging Service Database
-- ============================================
CREATE DATABASE IF NOT EXISTS charging_db;
USE charging_db;

CREATE TABLE IF NOT EXISTS service_fees (
    fee_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    booking_id INT NOT NULL,
    original_amount DECIMAL(10, 2) NOT NULL,
    service_fee DECIMAL(10, 2) NOT NULL,
    refund_amount DECIMAL(10, 2) NOT NULL,
    status ENUM('calculated', 'refund_initiated', 'refund_completed') DEFAULT 'calculated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_id (event_id),
    INDEX idx_booking_id (booking_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 9. Saga Log Database (Booking Orchestrator)
-- ============================================
CREATE DATABASE IF NOT EXISTS saga_log_db;
USE saga_log_db;

CREATE TABLE IF NOT EXISTS saga_log (
    saga_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    event_id INT NOT NULL,
    seat_id INT NULL,
    booking_id INT NULL,
    payment_intent_id VARCHAR(255) NULL,
    email VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NULL,
    status ENUM('STARTED', 'SEAT_RESERVED', 'PAYMENT_PENDING', 'PAYMENT_SUCCESS', 'CONFIRMED', 'FAILED', 'TIMEOUT') DEFAULT 'STARTED',
    error_message TEXT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status_expires (status, expires_at),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- Seed Data
-- ============================================

-- ----- Events -----
USE event_db;

INSERT INTO events (name, description, category, event_date, venue, status, total_seats, available_seats, price_min, price_max, image_url) VALUES
('Taylor Swift: The Eras Tour Singapore', 'Experience the magic of Taylor Swift live at the National Stadium. A journey through all musical eras.', 'Concert', '2026-06-15 19:30:00', 'National Stadium, Singapore', 'upcoming', 1500, 1500, 88.00, 388.00, NULL),
('Ed Sheeran: Mathematics Tour', 'Ed Sheeran brings his Mathematics Tour to Singapore for an unforgettable night of music.', 'Concert', '2026-07-20 20:00:00', 'Singapore Indoor Stadium', 'upcoming', 800, 800, 128.00, 328.00, NULL),
('Coldplay: Music of the Spheres', 'Coldplay returns to Singapore with their spectacular Music of the Spheres world tour.', 'Concert', '2026-08-10 19:00:00', 'National Stadium, Singapore', 'upcoming', 2000, 2000, 98.00, 358.00, NULL),
('Jay Chou: Carnival World Tour', 'The King of Mandopop Jay Chou performs his greatest hits live in Singapore.', 'Concert', '2026-05-25 20:00:00', 'Singapore Indoor Stadium', 'ongoing', 1000, 1000, 108.00, 368.00, NULL),
('Blackpink: Born Pink Finale', 'Blackpink concludes their world tour with a spectacular finale in Singapore.', 'Concert', '2026-09-05 19:30:00', 'National Stadium, Singapore', 'upcoming', 1800, 1800, 118.00, 388.00, NULL);

-- ----- Sections and Seats -----
USE seat_db;

-- Event 1: Taylor Swift (event_id=1)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(1, 'VIP', 388.00, 30, 30),
(1, 'CAT1', 248.00, 50, 50),
(1, 'CAT2', 88.00, 50, 50);

-- Event 2: Ed Sheeran (event_id=2)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(2, 'VIP', 328.00, 20, 20),
(2, 'CAT1', 228.00, 40, 40),
(2, 'CAT2', 128.00, 40, 40);

-- Event 3: Coldplay (event_id=3)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(3, 'VIP', 358.00, 30, 30),
(3, 'CAT1', 238.00, 50, 50),
(3, 'CAT2', 98.00, 50, 50);

-- Event 4: Jay Chou (event_id=4)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(4, 'VIP', 368.00, 25, 25),
(4, 'CAT1', 248.00, 40, 40),
(4, 'CAT2', 108.00, 40, 40);

-- Event 5: Blackpink (event_id=5)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(5, 'VIP', 388.00, 30, 30),
(5, 'CAT1', 258.00, 50, 50),
(5, 'CAT2', 118.00, 50, 50);

-- Seats for Event 1: Taylor Swift
-- VIP section (section_id=1)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(1, 1, 'VIP-001', 'available'), (1, 1, 'VIP-002', 'available'), (1, 1, 'VIP-003', 'available'),
(1, 1, 'VIP-004', 'available'), (1, 1, 'VIP-005', 'available'), (1, 1, 'VIP-006', 'available'),
(1, 1, 'VIP-007', 'available'), (1, 1, 'VIP-008', 'available'), (1, 1, 'VIP-009', 'available'),
(1, 1, 'VIP-010', 'available'), (1, 1, 'VIP-011', 'available'), (1, 1, 'VIP-012', 'available'),
(1, 1, 'VIP-013', 'available'), (1, 1, 'VIP-014', 'available'), (1, 1, 'VIP-015', 'available'),
(1, 1, 'VIP-016', 'available'), (1, 1, 'VIP-017', 'available'), (1, 1, 'VIP-018', 'available'),
(1, 1, 'VIP-019', 'available'), (1, 1, 'VIP-020', 'available'), (1, 1, 'VIP-021', 'available'),
(1, 1, 'VIP-022', 'available'), (1, 1, 'VIP-023', 'available'), (1, 1, 'VIP-024', 'available'),
(1, 1, 'VIP-025', 'available'), (1, 1, 'VIP-026', 'available'), (1, 1, 'VIP-027', 'available'),
(1, 1, 'VIP-028', 'available'), (1, 1, 'VIP-029', 'available'), (1, 1, 'VIP-030', 'available');

-- CAT1 section (section_id=2)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(1, 2, 'A-001', 'available'), (1, 2, 'A-002', 'available'), (1, 2, 'A-003', 'available'),
(1, 2, 'A-004', 'available'), (1, 2, 'A-005', 'available'), (1, 2, 'A-006', 'available'),
(1, 2, 'A-007', 'available'), (1, 2, 'A-008', 'available'), (1, 2, 'A-009', 'available'),
(1, 2, 'A-010', 'available'), (1, 2, 'A-011', 'available'), (1, 2, 'A-012', 'available'),
(1, 2, 'A-013', 'available'), (1, 2, 'A-014', 'available'), (1, 2, 'A-015', 'available'),
(1, 2, 'A-016', 'available'), (1, 2, 'A-017', 'available'), (1, 2, 'A-018', 'available'),
(1, 2, 'A-019', 'available'), (1, 2, 'A-020', 'available'), (1, 2, 'A-021', 'available'),
(1, 2, 'A-022', 'available'), (1, 2, 'A-023', 'available'), (1, 2, 'A-024', 'available'),
(1, 2, 'A-025', 'available'), (1, 2, 'A-026', 'available'), (1, 2, 'A-027', 'available'),
(1, 2, 'A-028', 'available'), (1, 2, 'A-029', 'available'), (1, 2, 'A-030', 'available'),
(1, 2, 'A-031', 'available'), (1, 2, 'A-032', 'available'), (1, 2, 'A-033', 'available'),
(1, 2, 'A-034', 'available'), (1, 2, 'A-035', 'available'), (1, 2, 'A-036', 'available'),
(1, 2, 'A-037', 'available'), (1, 2, 'A-038', 'available'), (1, 2, 'A-039', 'available'),
(1, 2, 'A-040', 'available'), (1, 2, 'A-041', 'available'), (1, 2, 'A-042', 'available'),
(1, 2, 'A-043', 'available'), (1, 2, 'A-044', 'available'), (1, 2, 'A-045', 'available'),
(1, 2, 'A-046', 'available'), (1, 2, 'A-047', 'available'), (1, 2, 'A-048', 'available'),
(1, 2, 'A-049', 'available'), (1, 2, 'A-050', 'available');

-- CAT2 section (section_id=3)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(1, 3, 'B-001', 'available'), (1, 3, 'B-002', 'available'), (1, 3, 'B-003', 'available'),
(1, 3, 'B-004', 'available'), (1, 3, 'B-005', 'available'), (1, 3, 'B-006', 'available'),
(1, 3, 'B-007', 'available'), (1, 3, 'B-008', 'available'), (1, 3, 'B-009', 'available'),
(1, 3, 'B-010', 'available'), (1, 3, 'B-011', 'available'), (1, 3, 'B-012', 'available'),
(1, 3, 'B-013', 'available'), (1, 3, 'B-014', 'available'), (1, 3, 'B-015', 'available'),
(1, 3, 'B-016', 'available'), (1, 3, 'B-017', 'available'), (1, 3, 'B-018', 'available'),
(1, 3, 'B-019', 'available'), (1, 3, 'B-020', 'available'), (1, 3, 'B-021', 'available'),
(1, 3, 'B-022', 'available'), (1, 3, 'B-023', 'available'), (1, 3, 'B-024', 'available'),
(1, 3, 'B-025', 'available'), (1, 3, 'B-026', 'available'), (1, 3, 'B-027', 'available'),
(1, 3, 'B-028', 'available'), (1, 3, 'B-029', 'available'), (1, 3, 'B-030', 'available'),
(1, 3, 'B-031', 'available'), (1, 3, 'B-032', 'available'), (1, 3, 'B-033', 'available'),
(1, 3, 'B-034', 'available'), (1, 3, 'B-035', 'available'), (1, 3, 'B-036', 'available'),
(1, 3, 'B-037', 'available'), (1, 3, 'B-038', 'available'), (1, 3, 'B-039', 'available'),
(1, 3, 'B-040', 'available'), (1, 3, 'B-041', 'available'), (1, 3, 'B-042', 'available'),
(1, 3, 'B-043', 'available'), (1, 3, 'B-044', 'available'), (1, 3, 'B-045', 'available'),
(1, 3, 'B-046', 'available'), (1, 3, 'B-047', 'available'), (1, 3, 'B-048', 'available'),
(1, 3, 'B-049', 'available'), (1, 3, 'B-050', 'available');

-- Seats for Event 2: Ed Sheeran
-- VIP section (section_id=4)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(2, 4, 'VIP-001', 'available'), (2, 4, 'VIP-002', 'available'), (2, 4, 'VIP-003', 'available'),
(2, 4, 'VIP-004', 'available'), (2, 4, 'VIP-005', 'available'), (2, 4, 'VIP-006', 'available'),
(2, 4, 'VIP-007', 'available'), (2, 4, 'VIP-008', 'available'), (2, 4, 'VIP-009', 'available'),
(2, 4, 'VIP-010', 'available'), (2, 4, 'VIP-011', 'available'), (2, 4, 'VIP-012', 'available'),
(2, 4, 'VIP-013', 'available'), (2, 4, 'VIP-014', 'available'), (2, 4, 'VIP-015', 'available'),
(2, 4, 'VIP-016', 'available'), (2, 4, 'VIP-017', 'available'), (2, 4, 'VIP-018', 'available'),
(2, 4, 'VIP-019', 'available'), (2, 4, 'VIP-020', 'available');

-- CAT1 section (section_id=5)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(2, 5, 'A-001', 'available'), (2, 5, 'A-002', 'available'), (2, 5, 'A-003', 'available'),
(2, 5, 'A-004', 'available'), (2, 5, 'A-005', 'available'), (2, 5, 'A-006', 'available'),
(2, 5, 'A-007', 'available'), (2, 5, 'A-008', 'available'), (2, 5, 'A-009', 'available'),
(2, 5, 'A-010', 'available'), (2, 5, 'A-011', 'available'), (2, 5, 'A-012', 'available'),
(2, 5, 'A-013', 'available'), (2, 5, 'A-014', 'available'), (2, 5, 'A-015', 'available'),
(2, 5, 'A-016', 'available'), (2, 5, 'A-017', 'available'), (2, 5, 'A-018', 'available'),
(2, 5, 'A-019', 'available'), (2, 5, 'A-020', 'available'), (2, 5, 'A-021', 'available'),
(2, 5, 'A-022', 'available'), (2, 5, 'A-023', 'available'), (2, 5, 'A-024', 'available'),
(2, 5, 'A-025', 'available'), (2, 5, 'A-026', 'available'), (2, 5, 'A-027', 'available'),
(2, 5, 'A-028', 'available'), (2, 5, 'A-029', 'available'), (2, 5, 'A-030', 'available'),
(2, 5, 'A-031', 'available'), (2, 5, 'A-032', 'available'), (2, 5, 'A-033', 'available'),
(2, 5, 'A-034', 'available'), (2, 5, 'A-035', 'available'), (2, 5, 'A-036', 'available'),
(2, 5, 'A-037', 'available'), (2, 5, 'A-038', 'available'), (2, 5, 'A-039', 'available'),
(2, 5, 'A-040', 'available');

-- CAT2 section (section_id=6)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(2, 6, 'B-001', 'available'), (2, 6, 'B-002', 'available'), (2, 6, 'B-003', 'available'),
(2, 6, 'B-004', 'available'), (2, 6, 'B-005', 'available'), (2, 6, 'B-006', 'available'),
(2, 6, 'B-007', 'available'), (2, 6, 'B-008', 'available'), (2, 6, 'B-009', 'available'),
(2, 6, 'B-010', 'available'), (2, 6, 'B-011', 'available'), (2, 6, 'B-012', 'available'),
(2, 6, 'B-013', 'available'), (2, 6, 'B-014', 'available'), (2, 6, 'B-015', 'available'),
(2, 6, 'B-016', 'available'), (2, 6, 'B-017', 'available'), (2, 6, 'B-018', 'available'),
(2, 6, 'B-019', 'available'), (2, 6, 'B-020', 'available'), (2, 6, 'B-021', 'available'),
(2, 6, 'B-022', 'available'), (2, 6, 'B-023', 'available'), (2, 6, 'B-024', 'available'),
(2, 6, 'B-025', 'available'), (2, 6, 'B-026', 'available'), (2, 6, 'B-027', 'available'),
(2, 6, 'B-028', 'available'), (2, 6, 'B-029', 'available'), (2, 6, 'B-030', 'available'),
(2, 6, 'B-031', 'available'), (2, 6, 'B-032', 'available'), (2, 6, 'B-033', 'available'),
(2, 6, 'B-034', 'available'), (2, 6, 'B-035', 'available'), (2, 6, 'B-036', 'available'),
(2, 6, 'B-037', 'available'), (2, 6, 'B-038', 'available'), (2, 6, 'B-039', 'available'),
(2, 6, 'B-040', 'available');

-- Seats for Event 3: Coldplay
-- VIP section (section_id=7)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(3, 7, 'VIP-001', 'available'), (3, 7, 'VIP-002', 'available'), (3, 7, 'VIP-003', 'available'),
(3, 7, 'VIP-004', 'available'), (3, 7, 'VIP-005', 'available'), (3, 7, 'VIP-006', 'available'),
(3, 7, 'VIP-007', 'available'), (3, 7, 'VIP-008', 'available'), (3, 7, 'VIP-009', 'available'),
(3, 7, 'VIP-010', 'available'), (3, 7, 'VIP-011', 'available'), (3, 7, 'VIP-012', 'available'),
(3, 7, 'VIP-013', 'available'), (3, 7, 'VIP-014', 'available'), (3, 7, 'VIP-015', 'available'),
(3, 7, 'VIP-016', 'available'), (3, 7, 'VIP-017', 'available'), (3, 7, 'VIP-018', 'available'),
(3, 7, 'VIP-019', 'available'), (3, 7, 'VIP-020', 'available'), (3, 7, 'VIP-021', 'available'),
(3, 7, 'VIP-022', 'available'), (3, 7, 'VIP-023', 'available'), (3, 7, 'VIP-024', 'available'),
(3, 7, 'VIP-025', 'available'), (3, 7, 'VIP-026', 'available'), (3, 7, 'VIP-027', 'available'),
(3, 7, 'VIP-028', 'available'), (3, 7, 'VIP-029', 'available'), (3, 7, 'VIP-030', 'available');

-- CAT1 section (section_id=8)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(3, 8, 'A-001', 'available'), (3, 8, 'A-002', 'available'), (3, 8, 'A-003', 'available'),
(3, 8, 'A-004', 'available'), (3, 8, 'A-005', 'available'), (3, 8, 'A-006', 'available'),
(3, 8, 'A-007', 'available'), (3, 8, 'A-008', 'available'), (3, 8, 'A-009', 'available'),
(3, 8, 'A-010', 'available'), (3, 8, 'A-011', 'available'), (3, 8, 'A-012', 'available'),
(3, 8, 'A-013', 'available'), (3, 8, 'A-014', 'available'), (3, 8, 'A-015', 'available'),
(3, 8, 'A-016', 'available'), (3, 8, 'A-017', 'available'), (3, 8, 'A-018', 'available'),
(3, 8, 'A-019', 'available'), (3, 8, 'A-020', 'available'), (3, 8, 'A-021', 'available'),
(3, 8, 'A-022', 'available'), (3, 8, 'A-023', 'available'), (3, 8, 'A-024', 'available'),
(3, 8, 'A-025', 'available'), (3, 8, 'A-026', 'available'), (3, 8, 'A-027', 'available'),
(3, 8, 'A-028', 'available'), (3, 8, 'A-029', 'available'), (3, 8, 'A-030', 'available'),
(3, 8, 'A-031', 'available'), (3, 8, 'A-032', 'available'), (3, 8, 'A-033', 'available'),
(3, 8, 'A-034', 'available'), (3, 8, 'A-035', 'available'), (3, 8, 'A-036', 'available'),
(3, 8, 'A-037', 'available'), (3, 8, 'A-038', 'available'), (3, 8, 'A-039', 'available'),
(3, 8, 'A-040', 'available'), (3, 8, 'A-041', 'available'), (3, 8, 'A-042', 'available'),
(3, 8, 'A-043', 'available'), (3, 8, 'A-044', 'available'), (3, 8, 'A-045', 'available'),
(3, 8, 'A-046', 'available'), (3, 8, 'A-047', 'available'), (3, 8, 'A-048', 'available'),
(3, 8, 'A-049', 'available'), (3, 8, 'A-050', 'available');

-- CAT2 section (section_id=9)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(3, 9, 'B-001', 'available'), (3, 9, 'B-002', 'available'), (3, 9, 'B-003', 'available'),
(3, 9, 'B-004', 'available'), (3, 9, 'B-005', 'available'), (3, 9, 'B-006', 'available'),
(3, 9, 'B-007', 'available'), (3, 9, 'B-008', 'available'), (3, 9, 'B-009', 'available'),
(3, 9, 'B-010', 'available'), (3, 9, 'B-011', 'available'), (3, 9, 'B-012', 'available'),
(3, 9, 'B-013', 'available'), (3, 9, 'B-014', 'available'), (3, 9, 'B-015', 'available'),
(3, 9, 'B-016', 'available'), (3, 9, 'B-017', 'available'), (3, 9, 'B-018', 'available'),
(3, 9, 'B-019', 'available'), (3, 9, 'B-020', 'available'), (3, 9, 'B-021', 'available'),
(3, 9, 'B-022', 'available'), (3, 9, 'B-023', 'available'), (3, 9, 'B-024', 'available'),
(3, 9, 'B-025', 'available'), (3, 9, 'B-026', 'available'), (3, 9, 'B-027', 'available'),
(3, 9, 'B-028', 'available'), (3, 9, 'B-029', 'available'), (3, 9, 'B-030', 'available'),
(3, 9, 'B-031', 'available'), (3, 9, 'B-032', 'available'), (3, 9, 'B-033', 'available'),
(3, 9, 'B-034', 'available'), (3, 9, 'B-035', 'available'), (3, 9, 'B-036', 'available'),
(3, 9, 'B-037', 'available'), (3, 9, 'B-038', 'available'), (3, 9, 'B-039', 'available'),
(3, 9, 'B-040', 'available'), (3, 9, 'B-041', 'available'), (3, 9, 'B-042', 'available'),
(3, 9, 'B-043', 'available'), (3, 9, 'B-044', 'available'), (3, 9, 'B-045', 'available'),
(3, 9, 'B-046', 'available'), (3, 9, 'B-047', 'available'), (3, 9, 'B-048', 'available'),
(3, 9, 'B-049', 'available'), (3, 9, 'B-050', 'available');

-- Seats for Event 4: Jay Chou
-- VIP section (section_id=10)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(4, 10, 'VIP-001', 'available'), (4, 10, 'VIP-002', 'available'), (4, 10, 'VIP-003', 'available'),
(4, 10, 'VIP-004', 'available'), (4, 10, 'VIP-005', 'available'), (4, 10, 'VIP-006', 'available'),
(4, 10, 'VIP-007', 'available'), (4, 10, 'VIP-008', 'available'), (4, 10, 'VIP-009', 'available'),
(4, 10, 'VIP-010', 'available'), (4, 10, 'VIP-011', 'available'), (4, 10, 'VIP-012', 'available'),
(4, 10, 'VIP-013', 'available'), (4, 10, 'VIP-014', 'available'), (4, 10, 'VIP-015', 'available'),
(4, 10, 'VIP-016', 'available'), (4, 10, 'VIP-017', 'available'), (4, 10, 'VIP-018', 'available'),
(4, 10, 'VIP-019', 'available'), (4, 10, 'VIP-020', 'available'), (4, 10, 'VIP-021', 'available'),
(4, 10, 'VIP-022', 'available'), (4, 10, 'VIP-023', 'available'), (4, 10, 'VIP-024', 'available'),
(4, 10, 'VIP-025', 'available');

-- CAT1 section (section_id=11)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(4, 11, 'A-001', 'available'), (4, 11, 'A-002', 'available'), (4, 11, 'A-003', 'available'),
(4, 11, 'A-004', 'available'), (4, 11, 'A-005', 'available'), (4, 11, 'A-006', 'available'),
(4, 11, 'A-007', 'available'), (4, 11, 'A-008', 'available'), (4, 11, 'A-009', 'available'),
(4, 11, 'A-010', 'available'), (4, 11, 'A-011', 'available'), (4, 11, 'A-012', 'available'),
(4, 11, 'A-013', 'available'), (4, 11, 'A-014', 'available'), (4, 11, 'A-015', 'available'),
(4, 11, 'A-016', 'available'), (4, 11, 'A-017', 'available'), (4, 11, 'A-018', 'available'),
(4, 11, 'A-019', 'available'), (4, 11, 'A-020', 'available'), (4, 11, 'A-021', 'available'),
(4, 11, 'A-022', 'available'), (4, 11, 'A-023', 'available'), (4, 11, 'A-024', 'available'),
(4, 11, 'A-025', 'available'), (4, 11, 'A-026', 'available'), (4, 11, 'A-027', 'available'),
(4, 11, 'A-028', 'available'), (4, 11, 'A-029', 'available'), (4, 11, 'A-030', 'available'),
(4, 11, 'A-031', 'available'), (4, 11, 'A-032', 'available'), (4, 11, 'A-033', 'available'),
(4, 11, 'A-034', 'available'), (4, 11, 'A-035', 'available'), (4, 11, 'A-036', 'available'),
(4, 11, 'A-037', 'available'), (4, 11, 'A-038', 'available'), (4, 11, 'A-039', 'available'),
(4, 11, 'A-040', 'available');

-- CAT2 section (section_id=12)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(4, 12, 'B-001', 'available'), (4, 12, 'B-002', 'available'), (4, 12, 'B-003', 'available'),
(4, 12, 'B-004', 'available'), (4, 12, 'B-005', 'available'), (4, 12, 'B-006', 'available'),
(4, 12, 'B-007', 'available'), (4, 12, 'B-008', 'available'), (4, 12, 'B-009', 'available'),
(4, 12, 'B-010', 'available'), (4, 12, 'B-011', 'available'), (4, 12, 'B-012', 'available'),
(4, 12, 'B-013', 'available'), (4, 12, 'B-014', 'available'), (4, 12, 'B-015', 'available'),
(4, 12, 'B-016', 'available'), (4, 12, 'B-017', 'available'), (4, 12, 'B-018', 'available'),
(4, 12, 'B-019', 'available'), (4, 12, 'B-020', 'available'), (4, 12, 'B-021', 'available'),
(4, 12, 'B-022', 'available'), (4, 12, 'B-023', 'available'), (4, 12, 'B-024', 'available'),
(4, 12, 'B-025', 'available'), (4, 12, 'B-026', 'available'), (4, 12, 'B-027', 'available'),
(4, 12, 'B-028', 'available'), (4, 12, 'B-029', 'available'), (4, 12, 'B-030', 'available'),
(4, 12, 'B-031', 'available'), (4, 12, 'B-032', 'available'), (4, 12, 'B-033', 'available'),
(4, 12, 'B-034', 'available'), (4, 12, 'B-035', 'available'), (4, 12, 'B-036', 'available'),
(4, 12, 'B-037', 'available'), (4, 12, 'B-038', 'available'), (4, 12, 'B-039', 'available'),
(4, 12, 'B-040', 'available');

-- Seats for Event 5: Blackpink
-- VIP section (section_id=13)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(5, 13, 'VIP-001', 'available'), (5, 13, 'VIP-002', 'available'), (5, 13, 'VIP-003', 'available'),
(5, 13, 'VIP-004', 'available'), (5, 13, 'VIP-005', 'available'), (5, 13, 'VIP-006', 'available'),
(5, 13, 'VIP-007', 'available'), (5, 13, 'VIP-008', 'available'), (5, 13, 'VIP-009', 'available'),
(5, 13, 'VIP-010', 'available'), (5, 13, 'VIP-011', 'available'), (5, 13, 'VIP-012', 'available'),
(5, 13, 'VIP-013', 'available'), (5, 13, 'VIP-014', 'available'), (5, 13, 'VIP-015', 'available'),
(5, 13, 'VIP-016', 'available'), (5, 13, 'VIP-017', 'available'), (5, 13, 'VIP-018', 'available'),
(5, 13, 'VIP-019', 'available'), (5, 13, 'VIP-020', 'available'), (5, 13, 'VIP-021', 'available'),
(5, 13, 'VIP-022', 'available'), (5, 13, 'VIP-023', 'available'), (5, 13, 'VIP-024', 'available'),
(5, 13, 'VIP-025', 'available'), (5, 13, 'VIP-026', 'available'), (5, 13, 'VIP-027', 'available'),
(5, 13, 'VIP-028', 'available'), (5, 13, 'VIP-029', 'available'), (5, 13, 'VIP-030', 'available');

-- CAT1 section (section_id=14)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(5, 14, 'A-001', 'available'), (5, 14, 'A-002', 'available'), (5, 14, 'A-003', 'available'),
(5, 14, 'A-004', 'available'), (5, 14, 'A-005', 'available'), (5, 14, 'A-006', 'available'),
(5, 14, 'A-007', 'available'), (5, 14, 'A-008', 'available'), (5, 14, 'A-009', 'available'),
(5, 14, 'A-010', 'available'), (5, 14, 'A-011', 'available'), (5, 14, 'A-012', 'available'),
(5, 14, 'A-013', 'available'), (5, 14, 'A-014', 'available'), (5, 14, 'A-015', 'available'),
(5, 14, 'A-016', 'available'), (5, 14, 'A-017', 'available'), (5, 14, 'A-018', 'available'),
(5, 14, 'A-019', 'available'), (5, 14, 'A-020', 'available'), (5, 14, 'A-021', 'available'),
(5, 14, 'A-022', 'available'), (5, 14, 'A-023', 'available'), (5, 14, 'A-024', 'available'),
(5, 14, 'A-025', 'available'), (5, 14, 'A-026', 'available'), (5, 14, 'A-027', 'available'),
(5, 14, 'A-028', 'available'), (5, 14, 'A-029', 'available'), (5, 14, 'A-030', 'available'),
(5, 14, 'A-031', 'available'), (5, 14, 'A-032', 'available'), (5, 14, 'A-033', 'available'),
(5, 14, 'A-034', 'available'), (5, 14, 'A-035', 'available'), (5, 14, 'A-036', 'available'),
(5, 14, 'A-037', 'available'), (5, 14, 'A-038', 'available'), (5, 14, 'A-039', 'available'),
(5, 14, 'A-040', 'available'), (5, 14, 'A-041', 'available'), (5, 14, 'A-042', 'available'),
(5, 14, 'A-043', 'available'), (5, 14, 'A-044', 'available'), (5, 14, 'A-045', 'available'),
(5, 14, 'A-046', 'available'), (5, 14, 'A-047', 'available'), (5, 14, 'A-048', 'available'),
(5, 14, 'A-049', 'available'), (5, 14, 'A-050', 'available');

-- CAT2 section (section_id=15)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(5, 15, 'B-001', 'available'), (5, 15, 'B-002', 'available'), (5, 15, 'B-003', 'available'),
(5, 15, 'B-004', 'available'), (5, 15, 'B-005', 'available'), (5, 15, 'B-006', 'available'),
(5, 15, 'B-007', 'available'), (5, 15, 'B-008', 'available'), (5, 15, 'B-009', 'available'),
(5, 15, 'B-010', 'available'), (5, 15, 'B-011', 'available'), (5, 15, 'B-012', 'available'),
(5, 15, 'B-013', 'available'), (5, 15, 'B-014', 'available'), (5, 15, 'B-015', 'available'),
(5, 15, 'B-016', 'available'), (5, 15, 'B-017', 'available'), (5, 15, 'B-018', 'available'),
(5, 15, 'B-019', 'available'), (5, 15, 'B-020', 'available'), (5, 15, 'B-021', 'available'),
(5, 15, 'B-022', 'available'), (5, 15, 'B-023', 'available'), (5, 15, 'B-024', 'available'),
(5, 15, 'B-025', 'available'), (5, 15, 'B-026', 'available'), (5, 15, 'B-027', 'available'),
(5, 15, 'B-028', 'available'), (5, 15, 'B-029', 'available'), (5, 15, 'B-030', 'available'),
(5, 15, 'B-031', 'available'), (5, 15, 'B-032', 'available'), (5, 15, 'B-033', 'available'),
(5, 15, 'B-034', 'available'), (5, 15, 'B-035', 'available'), (5, 15, 'B-036', 'available'),
(5, 15, 'B-037', 'available'), (5, 15, 'B-038', 'available'), (5, 15, 'B-039', 'available'),
(5, 15, 'B-040', 'available'), (5, 15, 'B-041', 'available'), (5, 15, 'B-042', 'available'),
(5, 15, 'B-043', 'available'), (5, 15, 'B-044', 'available'), (5, 15, 'B-045', 'available'),
(5, 15, 'B-046', 'available'), (5, 15, 'B-047', 'available'), (5, 15, 'B-048', 'available'),
(5, 15, 'B-049', 'available'), (5, 15, 'B-050', 'available');
