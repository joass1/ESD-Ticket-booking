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
    price DECIMAL(29, 2) NOT NULL,
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
    amount DECIMAL(29, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'SGD',
    stripe_payment_intent_id VARCHAR(255),
    status ENUM('pending', 'succeeded', 'failed', 'refunded', 'refund_failed') DEFAULT 'pending',
    refund_amount DECIMAL(29, 2) NULL,
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
    original_amount DECIMAL(29, 2) NOT NULL,
    service_fee DECIMAL(29, 2) NOT NULL,
    refund_amount DECIMAL(29, 2) NOT NULL,
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
    phone VARCHAR(20) NULL,
    amount DECIMAL(29, 2) NULL,
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
('Taylor Swift: The Eras Tour Singapore', 'Experience the magic of Taylor Swift live at the National Stadium. A journey through all musical eras featuring hits from Fearless to Midnights.', 'Concert', '2026-06-15 19:30:00', 'National Stadium, Singapore', 'upcoming', 1500, 1500, 88.00, 388.00, 'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?w=800'),
('Ed Sheeran: Mathematics Tour', 'Ed Sheeran brings his Mathematics Tour to Singapore for an intimate and unforgettable night of acoustic magic.', 'Concert', '2026-07-20 20:00:00', 'Singapore Indoor Stadium', 'upcoming', 800, 800, 128.00, 328.00, 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=800'),
('Coldplay: Music of the Spheres', 'Coldplay returns to Singapore with their spectacular Music of the Spheres world tour, featuring dazzling LED wristbands and a breathtaking light show.', 'Concert', '2026-08-10 19:00:00', 'National Stadium, Singapore', 'upcoming', 2000, 2000, 98.00, 358.00, 'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800'),
('Jay Chou: Carnival World Tour', 'The King of Mandopop Jay Chou performs his greatest hits live in Singapore. An electrifying night of Mandarin pop at its finest.', 'Concert', '2026-05-25 20:00:00', 'Singapore Indoor Stadium', 'ongoing', 1000, 1000, 108.00, 368.00, 'https://images.unsplash.com/photo-1429962714451-bb934ecdc4ec?w=800'),
('Blackpink: Born Pink Finale', 'Blackpink concludes their record-breaking world tour with a spectacular finale in Singapore. K-pop history in the making.', 'Concert', '2026-09-05 19:30:00', 'National Stadium, Singapore', 'upcoming', 1800, 1800, 118.00, 388.00, 'https://images.unsplash.com/photo-1493676304819-0d7a8d026dcf?w=800'),
('Singapore Grand Prix: F1 Night Race', 'The only night race on the F1 calendar. Watch the world''s fastest drivers battle it out under the lights on the iconic Marina Bay Street Circuit.', 'Sports', '2026-10-03 20:00:00', 'Marina Bay Street Circuit, Singapore', 'upcoming', 1200, 1200, 148.00, 588.00, 'https://images.unsplash.com/photo-1504817343863-5092a923803e?w=800'),
('The Phantom of the Opera', 'Andrew Lloyd Webber''s legendary musical returns to Singapore. Experience the grandeur, romance, and mystery of the longest-running show in Broadway history.', 'Theatre', '2026-07-05 19:30:00', 'Esplanade Theatre, Singapore', 'upcoming', 600, 600, 68.00, 258.00, 'https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?w=800'),
('Russell Peters: Live in Singapore', 'Comedy superstar Russell Peters brings his razor-sharp observational humour to Singapore for one night only. Prepare to laugh until it hurts.', 'Comedy', '2026-06-28 20:00:00', 'The Star Theatre, Singapore', 'upcoming', 500, 500, 78.00, 198.00, 'https://images.unsplash.com/photo-1527224538127-2104bb71c51b?w=800'),
('Singapore International Jazz Festival', 'A weekend of world-class jazz featuring Grammy-winning artists and rising stars from across the globe. Three stages, two days, one unforgettable experience.', 'Festival', '2026-08-22 17:00:00', 'Marina Bay Sands Expo, Singapore', 'upcoming', 1000, 1000, 88.00, 288.00, 'https://images.unsplash.com/photo-1511192336575-5a79af67a629?w=800'),
('Bruno Mars: 24K Magic World Tour', 'The multi-Grammy winner Bruno Mars brings his electrifying stage presence and chart-topping hits to Singapore for an explosive night of funk, soul, and pop.', 'Concert', '2026-11-15 20:00:00', 'National Stadium, Singapore', 'upcoming', 1600, 1600, 108.00, 398.00, 'https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=800');

-- ----- Sections and Seats -----
USE seat_db;

-- Event 1: Taylor Swift (event_id=30)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(30, 'VIP', 388.00, 30, 30),
(30, 'CAT1', 248.00, 50, 50),
(30, 'CAT2', 88.00, 50, 50);

-- Event 2: Ed Sheeran (event_id=20)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(20, 'VIP', 328.00, 20, 20),
(20, 'CAT1', 228.00, 40, 40),
(20, 'CAT2', 128.00, 40, 40);

-- Event 3: Coldplay (event_id=22)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(22, 'VIP', 358.00, 30, 30),
(22, 'CAT1', 238.00, 50, 50),
(22, 'CAT2', 98.00, 50, 50);

-- Event 4: Jay Chou (event_id=23)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(23, 'VIP', 368.00, 25, 25),
(23, 'CAT1', 248.00, 40, 40),
(23, 'CAT2', 108.00, 40, 40);

-- Event 5: Blackpink (event_id=24)
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(24, 'VIP', 388.00, 30, 30),
(24, 'CAT1', 258.00, 50, 50),
(24, 'CAT2', 118.00, 50, 50);

-- Seats for Event 1: Taylor Swift
-- VIP section (section_id=1)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(30, 1, 'VIP-001', 'available'), (30, 1, 'VIP-002', 'available'), (30, 1, 'VIP-003', 'available'),
(30, 1, 'VIP-004', 'available'), (30, 1, 'VIP-005', 'available'), (30, 1, 'VIP-006', 'available'),
(30, 1, 'VIP-007', 'available'), (30, 1, 'VIP-008', 'available'), (30, 1, 'VIP-009', 'available'),
(30, 1, 'VIP-010', 'available'), (30, 1, 'VIP-011', 'available'), (30, 1, 'VIP-012', 'available'),
(30, 1, 'VIP-013', 'available'), (30, 1, 'VIP-014', 'available'), (30, 1, 'VIP-015', 'available'),
(30, 1, 'VIP-016', 'available'), (30, 1, 'VIP-017', 'available'), (30, 1, 'VIP-018', 'available'),
(30, 1, 'VIP-019', 'available'), (30, 1, 'VIP-020', 'available'), (30, 1, 'VIP-021', 'available'),
(30, 1, 'VIP-022', 'available'), (30, 1, 'VIP-023', 'available'), (30, 1, 'VIP-024', 'available'),
(30, 1, 'VIP-025', 'available'), (30, 1, 'VIP-026', 'available'), (30, 1, 'VIP-027', 'available'),
(30, 1, 'VIP-028', 'available'), (30, 1, 'VIP-029', 'available'), (30, 1, 'VIP-030', 'available');

-- CAT1 section (section_id=2)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(30, 2, 'A-001', 'available'), (30, 2, 'A-002', 'available'), (30, 2, 'A-003', 'available'),
(30, 2, 'A-004', 'available'), (30, 2, 'A-005', 'available'), (30, 2, 'A-006', 'available'),
(30, 2, 'A-007', 'available'), (30, 2, 'A-008', 'available'), (30, 2, 'A-009', 'available'),
(30, 2, 'A-010', 'available'), (30, 2, 'A-011', 'available'), (30, 2, 'A-012', 'available'),
(30, 2, 'A-013', 'available'), (30, 2, 'A-014', 'available'), (30, 2, 'A-015', 'available'),
(30, 2, 'A-016', 'available'), (30, 2, 'A-017', 'available'), (30, 2, 'A-018', 'available'),
(30, 2, 'A-019', 'available'), (30, 2, 'A-020', 'available'), (30, 2, 'A-021', 'available'),
(30, 2, 'A-022', 'available'), (30, 2, 'A-023', 'available'), (30, 2, 'A-024', 'available'),
(30, 2, 'A-025', 'available'), (30, 2, 'A-026', 'available'), (30, 2, 'A-027', 'available'),
(30, 2, 'A-028', 'available'), (30, 2, 'A-029', 'available'), (30, 2, 'A-030', 'available'),
(30, 2, 'A-031', 'available'), (30, 2, 'A-032', 'available'), (30, 2, 'A-033', 'available'),
(30, 2, 'A-034', 'available'), (30, 2, 'A-035', 'available'), (30, 2, 'A-036', 'available'),
(30, 2, 'A-037', 'available'), (30, 2, 'A-038', 'available'), (30, 2, 'A-039', 'available'),
(30, 2, 'A-040', 'available'), (30, 2, 'A-041', 'available'), (30, 2, 'A-042', 'available'),
(30, 2, 'A-043', 'available'), (30, 2, 'A-044', 'available'), (30, 2, 'A-045', 'available'),
(30, 2, 'A-046', 'available'), (30, 2, 'A-047', 'available'), (30, 2, 'A-048', 'available'),
(30, 2, 'A-049', 'available'), (30, 2, 'A-050', 'available');

-- CAT2 section (section_id=3)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(30, 3, 'B-001', 'available'), (30, 3, 'B-002', 'available'), (30, 3, 'B-003', 'available'),
(30, 3, 'B-004', 'available'), (30, 3, 'B-005', 'available'), (30, 3, 'B-006', 'available'),
(30, 3, 'B-007', 'available'), (30, 3, 'B-008', 'available'), (30, 3, 'B-009', 'available'),
(30, 3, 'B-010', 'available'), (30, 3, 'B-011', 'available'), (30, 3, 'B-012', 'available'),
(30, 3, 'B-013', 'available'), (30, 3, 'B-014', 'available'), (30, 3, 'B-015', 'available'),
(30, 3, 'B-016', 'available'), (30, 3, 'B-017', 'available'), (30, 3, 'B-018', 'available'),
(30, 3, 'B-019', 'available'), (30, 3, 'B-020', 'available'), (30, 3, 'B-021', 'available'),
(30, 3, 'B-022', 'available'), (30, 3, 'B-023', 'available'), (30, 3, 'B-024', 'available'),
(30, 3, 'B-025', 'available'), (30, 3, 'B-026', 'available'), (30, 3, 'B-027', 'available'),
(30, 3, 'B-028', 'available'), (30, 3, 'B-029', 'available'), (30, 3, 'B-030', 'available'),
(30, 3, 'B-031', 'available'), (30, 3, 'B-032', 'available'), (30, 3, 'B-033', 'available'),
(30, 3, 'B-034', 'available'), (30, 3, 'B-035', 'available'), (30, 3, 'B-036', 'available'),
(30, 3, 'B-037', 'available'), (30, 3, 'B-038', 'available'), (30, 3, 'B-039', 'available'),
(30, 3, 'B-040', 'available'), (30, 3, 'B-041', 'available'), (30, 3, 'B-042', 'available'),
(30, 3, 'B-043', 'available'), (30, 3, 'B-044', 'available'), (30, 3, 'B-045', 'available'),
(30, 3, 'B-046', 'available'), (30, 3, 'B-047', 'available'), (30, 3, 'B-048', 'available'),
(30, 3, 'B-049', 'available'), (30, 3, 'B-050', 'available');

-- Seats for Event 2: Ed Sheeran
-- VIP section (section_id=4)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(20, 4, 'VIP-001', 'available'), (20, 4, 'VIP-002', 'available'), (20, 4, 'VIP-003', 'available'),
(20, 4, 'VIP-004', 'available'), (20, 4, 'VIP-005', 'available'), (20, 4, 'VIP-006', 'available'),
(20, 4, 'VIP-007', 'available'), (20, 4, 'VIP-008', 'available'), (20, 4, 'VIP-009', 'available'),
(20, 4, 'VIP-010', 'available'), (20, 4, 'VIP-011', 'available'), (20, 4, 'VIP-012', 'available'),
(20, 4, 'VIP-013', 'available'), (20, 4, 'VIP-014', 'available'), (20, 4, 'VIP-015', 'available'),
(20, 4, 'VIP-016', 'available'), (20, 4, 'VIP-017', 'available'), (20, 4, 'VIP-018', 'available'),
(20, 4, 'VIP-019', 'available'), (20, 4, 'VIP-020', 'available');

-- CAT1 section (section_id=5)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(20, 5, 'A-001', 'available'), (20, 5, 'A-002', 'available'), (20, 5, 'A-003', 'available'),
(20, 5, 'A-004', 'available'), (20, 5, 'A-005', 'available'), (20, 5, 'A-006', 'available'),
(20, 5, 'A-007', 'available'), (20, 5, 'A-008', 'available'), (20, 5, 'A-009', 'available'),
(20, 5, 'A-010', 'available'), (20, 5, 'A-011', 'available'), (20, 5, 'A-012', 'available'),
(20, 5, 'A-013', 'available'), (20, 5, 'A-014', 'available'), (20, 5, 'A-015', 'available'),
(20, 5, 'A-016', 'available'), (20, 5, 'A-017', 'available'), (20, 5, 'A-018', 'available'),
(20, 5, 'A-019', 'available'), (20, 5, 'A-020', 'available'), (20, 5, 'A-021', 'available'),
(20, 5, 'A-022', 'available'), (20, 5, 'A-023', 'available'), (20, 5, 'A-024', 'available'),
(20, 5, 'A-025', 'available'), (20, 5, 'A-026', 'available'), (20, 5, 'A-027', 'available'),
(20, 5, 'A-028', 'available'), (20, 5, 'A-029', 'available'), (20, 5, 'A-030', 'available'),
(20, 5, 'A-031', 'available'), (20, 5, 'A-032', 'available'), (20, 5, 'A-033', 'available'),
(20, 5, 'A-034', 'available'), (20, 5, 'A-035', 'available'), (20, 5, 'A-036', 'available'),
(20, 5, 'A-037', 'available'), (20, 5, 'A-038', 'available'), (20, 5, 'A-039', 'available'),
(20, 5, 'A-040', 'available');

-- CAT2 section (section_id=6)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(20, 6, 'B-001', 'available'), (20, 6, 'B-002', 'available'), (20, 6, 'B-003', 'available'),
(20, 6, 'B-004', 'available'), (20, 6, 'B-005', 'available'), (20, 6, 'B-006', 'available'),
(20, 6, 'B-007', 'available'), (20, 6, 'B-008', 'available'), (20, 6, 'B-009', 'available'),
(20, 6, 'B-010', 'available'), (20, 6, 'B-011', 'available'), (20, 6, 'B-012', 'available'),
(20, 6, 'B-013', 'available'), (20, 6, 'B-014', 'available'), (20, 6, 'B-015', 'available'),
(20, 6, 'B-016', 'available'), (20, 6, 'B-017', 'available'), (20, 6, 'B-018', 'available'),
(20, 6, 'B-019', 'available'), (20, 6, 'B-020', 'available'), (20, 6, 'B-021', 'available'),
(20, 6, 'B-022', 'available'), (20, 6, 'B-023', 'available'), (20, 6, 'B-024', 'available'),
(20, 6, 'B-025', 'available'), (20, 6, 'B-026', 'available'), (20, 6, 'B-027', 'available'),
(20, 6, 'B-028', 'available'), (20, 6, 'B-029', 'available'), (20, 6, 'B-030', 'available'),
(20, 6, 'B-031', 'available'), (20, 6, 'B-032', 'available'), (20, 6, 'B-033', 'available'),
(20, 6, 'B-034', 'available'), (20, 6, 'B-035', 'available'), (20, 6, 'B-036', 'available'),
(20, 6, 'B-037', 'available'), (20, 6, 'B-038', 'available'), (20, 6, 'B-039', 'available'),
(20, 6, 'B-040', 'available');

-- Seats for Event 3: Coldplay
-- VIP section (section_id=7)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(22, 7, 'VIP-001', 'available'), (22, 7, 'VIP-002', 'available'), (22, 7, 'VIP-003', 'available'),
(22, 7, 'VIP-004', 'available'), (22, 7, 'VIP-005', 'available'), (22, 7, 'VIP-006', 'available'),
(22, 7, 'VIP-007', 'available'), (22, 7, 'VIP-008', 'available'), (22, 7, 'VIP-009', 'available'),
(22, 7, 'VIP-010', 'available'), (22, 7, 'VIP-011', 'available'), (22, 7, 'VIP-012', 'available'),
(22, 7, 'VIP-013', 'available'), (22, 7, 'VIP-014', 'available'), (22, 7, 'VIP-015', 'available'),
(22, 7, 'VIP-016', 'available'), (22, 7, 'VIP-017', 'available'), (22, 7, 'VIP-018', 'available'),
(22, 7, 'VIP-019', 'available'), (22, 7, 'VIP-020', 'available'), (22, 7, 'VIP-021', 'available'),
(22, 7, 'VIP-022', 'available'), (22, 7, 'VIP-023', 'available'), (22, 7, 'VIP-024', 'available'),
(22, 7, 'VIP-025', 'available'), (22, 7, 'VIP-026', 'available'), (22, 7, 'VIP-027', 'available'),
(22, 7, 'VIP-028', 'available'), (22, 7, 'VIP-029', 'available'), (22, 7, 'VIP-030', 'available');

-- CAT1 section (section_id=8)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(22, 8, 'A-001', 'available'), (22, 8, 'A-002', 'available'), (22, 8, 'A-003', 'available'),
(22, 8, 'A-004', 'available'), (22, 8, 'A-005', 'available'), (22, 8, 'A-006', 'available'),
(22, 8, 'A-007', 'available'), (22, 8, 'A-008', 'available'), (22, 8, 'A-009', 'available'),
(22, 8, 'A-010', 'available'), (22, 8, 'A-011', 'available'), (22, 8, 'A-012', 'available'),
(22, 8, 'A-013', 'available'), (22, 8, 'A-014', 'available'), (22, 8, 'A-015', 'available'),
(22, 8, 'A-016', 'available'), (22, 8, 'A-017', 'available'), (22, 8, 'A-018', 'available'),
(22, 8, 'A-019', 'available'), (22, 8, 'A-020', 'available'), (22, 8, 'A-021', 'available'),
(22, 8, 'A-022', 'available'), (22, 8, 'A-023', 'available'), (22, 8, 'A-024', 'available'),
(22, 8, 'A-025', 'available'), (22, 8, 'A-026', 'available'), (22, 8, 'A-027', 'available'),
(22, 8, 'A-028', 'available'), (22, 8, 'A-029', 'available'), (22, 8, 'A-030', 'available'),
(22, 8, 'A-031', 'available'), (22, 8, 'A-032', 'available'), (22, 8, 'A-033', 'available'),
(22, 8, 'A-034', 'available'), (22, 8, 'A-035', 'available'), (22, 8, 'A-036', 'available'),
(22, 8, 'A-037', 'available'), (22, 8, 'A-038', 'available'), (22, 8, 'A-039', 'available'),
(22, 8, 'A-040', 'available'), (22, 8, 'A-041', 'available'), (22, 8, 'A-042', 'available'),
(22, 8, 'A-043', 'available'), (22, 8, 'A-044', 'available'), (22, 8, 'A-045', 'available'),
(22, 8, 'A-046', 'available'), (22, 8, 'A-047', 'available'), (22, 8, 'A-048', 'available'),
(22, 8, 'A-049', 'available'), (22, 8, 'A-050', 'available');

-- CAT2 section (section_id=9)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(22, 9, 'B-001', 'available'), (22, 9, 'B-002', 'available'), (22, 9, 'B-003', 'available'),
(22, 9, 'B-004', 'available'), (22, 9, 'B-005', 'available'), (22, 9, 'B-006', 'available'),
(22, 9, 'B-007', 'available'), (22, 9, 'B-008', 'available'), (22, 9, 'B-009', 'available'),
(22, 9, 'B-010', 'available'), (22, 9, 'B-011', 'available'), (22, 9, 'B-012', 'available'),
(22, 9, 'B-013', 'available'), (22, 9, 'B-014', 'available'), (22, 9, 'B-015', 'available'),
(22, 9, 'B-016', 'available'), (22, 9, 'B-017', 'available'), (22, 9, 'B-018', 'available'),
(22, 9, 'B-019', 'available'), (22, 9, 'B-020', 'available'), (22, 9, 'B-021', 'available'),
(22, 9, 'B-022', 'available'), (22, 9, 'B-023', 'available'), (22, 9, 'B-024', 'available'),
(22, 9, 'B-025', 'available'), (22, 9, 'B-026', 'available'), (22, 9, 'B-027', 'available'),
(22, 9, 'B-028', 'available'), (22, 9, 'B-029', 'available'), (22, 9, 'B-030', 'available'),
(22, 9, 'B-031', 'available'), (22, 9, 'B-032', 'available'), (22, 9, 'B-033', 'available'),
(22, 9, 'B-034', 'available'), (22, 9, 'B-035', 'available'), (22, 9, 'B-036', 'available'),
(22, 9, 'B-037', 'available'), (22, 9, 'B-038', 'available'), (22, 9, 'B-039', 'available'),
(22, 9, 'B-040', 'available'), (22, 9, 'B-041', 'available'), (22, 9, 'B-042', 'available'),
(22, 9, 'B-043', 'available'), (22, 9, 'B-044', 'available'), (22, 9, 'B-045', 'available'),
(22, 9, 'B-046', 'available'), (22, 9, 'B-047', 'available'), (22, 9, 'B-048', 'available'),
(22, 9, 'B-049', 'available'), (22, 9, 'B-050', 'available');

-- Seats for Event 4: Jay Chou
-- VIP section (section_id=10)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(23, 10, 'VIP-001', 'available'), (23, 10, 'VIP-002', 'available'), (23, 10, 'VIP-003', 'available'),
(23, 10, 'VIP-004', 'available'), (23, 10, 'VIP-005', 'available'), (23, 10, 'VIP-006', 'available'),
(23, 10, 'VIP-007', 'available'), (23, 10, 'VIP-008', 'available'), (23, 10, 'VIP-009', 'available'),
(23, 10, 'VIP-010', 'available'), (23, 10, 'VIP-011', 'available'), (23, 10, 'VIP-012', 'available'),
(23, 10, 'VIP-013', 'available'), (23, 10, 'VIP-014', 'available'), (23, 10, 'VIP-015', 'available'),
(23, 10, 'VIP-016', 'available'), (23, 10, 'VIP-017', 'available'), (23, 10, 'VIP-018', 'available'),
(23, 10, 'VIP-019', 'available'), (23, 10, 'VIP-020', 'available'), (23, 10, 'VIP-021', 'available'),
(23, 10, 'VIP-022', 'available'), (23, 10, 'VIP-023', 'available'), (23, 10, 'VIP-024', 'available'),
(23, 10, 'VIP-025', 'available');

-- CAT1 section (section_id=11)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(23, 11, 'A-001', 'available'), (23, 11, 'A-002', 'available'), (23, 11, 'A-003', 'available'),
(23, 11, 'A-004', 'available'), (23, 11, 'A-005', 'available'), (23, 11, 'A-006', 'available'),
(23, 11, 'A-007', 'available'), (23, 11, 'A-008', 'available'), (23, 11, 'A-009', 'available'),
(23, 11, 'A-010', 'available'), (23, 11, 'A-011', 'available'), (23, 11, 'A-012', 'available'),
(23, 11, 'A-013', 'available'), (23, 11, 'A-014', 'available'), (23, 11, 'A-015', 'available'),
(23, 11, 'A-016', 'available'), (23, 11, 'A-017', 'available'), (23, 11, 'A-018', 'available'),
(23, 11, 'A-019', 'available'), (23, 11, 'A-020', 'available'), (23, 11, 'A-021', 'available'),
(23, 11, 'A-022', 'available'), (23, 11, 'A-023', 'available'), (23, 11, 'A-024', 'available'),
(23, 11, 'A-025', 'available'), (23, 11, 'A-026', 'available'), (23, 11, 'A-027', 'available'),
(23, 11, 'A-028', 'available'), (23, 11, 'A-029', 'available'), (23, 11, 'A-030', 'available'),
(23, 11, 'A-031', 'available'), (23, 11, 'A-032', 'available'), (23, 11, 'A-033', 'available'),
(23, 11, 'A-034', 'available'), (23, 11, 'A-035', 'available'), (23, 11, 'A-036', 'available'),
(23, 11, 'A-037', 'available'), (23, 11, 'A-038', 'available'), (23, 11, 'A-039', 'available'),
(23, 11, 'A-040', 'available');

-- CAT2 section (section_id=12)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(23, 12, 'B-001', 'available'), (23, 12, 'B-002', 'available'), (23, 12, 'B-003', 'available'),
(23, 12, 'B-004', 'available'), (23, 12, 'B-005', 'available'), (23, 12, 'B-006', 'available'),
(23, 12, 'B-007', 'available'), (23, 12, 'B-008', 'available'), (23, 12, 'B-009', 'available'),
(23, 12, 'B-010', 'available'), (23, 12, 'B-011', 'available'), (23, 12, 'B-012', 'available'),
(23, 12, 'B-013', 'available'), (23, 12, 'B-014', 'available'), (23, 12, 'B-015', 'available'),
(23, 12, 'B-016', 'available'), (23, 12, 'B-017', 'available'), (23, 12, 'B-018', 'available'),
(23, 12, 'B-019', 'available'), (23, 12, 'B-020', 'available'), (23, 12, 'B-021', 'available'),
(23, 12, 'B-022', 'available'), (23, 12, 'B-023', 'available'), (23, 12, 'B-024', 'available'),
(23, 12, 'B-025', 'available'), (23, 12, 'B-026', 'available'), (23, 12, 'B-027', 'available'),
(23, 12, 'B-028', 'available'), (23, 12, 'B-029', 'available'), (23, 12, 'B-030', 'available'),
(23, 12, 'B-031', 'available'), (23, 12, 'B-032', 'available'), (23, 12, 'B-033', 'available'),
(23, 12, 'B-034', 'available'), (23, 12, 'B-035', 'available'), (23, 12, 'B-036', 'available'),
(23, 12, 'B-037', 'available'), (23, 12, 'B-038', 'available'), (23, 12, 'B-039', 'available'),
(23, 12, 'B-040', 'available');

-- Seats for Event 5: Blackpink
-- VIP section (section_id=13)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(24, 13, 'VIP-001', 'available'), (24, 13, 'VIP-002', 'available'), (24, 13, 'VIP-003', 'available'),
(24, 13, 'VIP-004', 'available'), (24, 13, 'VIP-005', 'available'), (24, 13, 'VIP-006', 'available'),
(24, 13, 'VIP-007', 'available'), (24, 13, 'VIP-008', 'available'), (24, 13, 'VIP-009', 'available'),
(24, 13, 'VIP-010', 'available'), (24, 13, 'VIP-011', 'available'), (24, 13, 'VIP-012', 'available'),
(24, 13, 'VIP-013', 'available'), (24, 13, 'VIP-014', 'available'), (24, 13, 'VIP-015', 'available'),
(24, 13, 'VIP-016', 'available'), (24, 13, 'VIP-017', 'available'), (24, 13, 'VIP-018', 'available'),
(24, 13, 'VIP-019', 'available'), (24, 13, 'VIP-020', 'available'), (24, 13, 'VIP-021', 'available'),
(24, 13, 'VIP-022', 'available'), (24, 13, 'VIP-023', 'available'), (24, 13, 'VIP-024', 'available'),
(24, 13, 'VIP-025', 'available'), (24, 13, 'VIP-026', 'available'), (24, 13, 'VIP-027', 'available'),
(24, 13, 'VIP-028', 'available'), (24, 13, 'VIP-029', 'available'), (24, 13, 'VIP-030', 'available');

-- CAT1 section (section_id=14)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(24, 14, 'A-001', 'available'), (24, 14, 'A-002', 'available'), (24, 14, 'A-003', 'available'),
(24, 14, 'A-004', 'available'), (24, 14, 'A-005', 'available'), (24, 14, 'A-006', 'available'),
(24, 14, 'A-007', 'available'), (24, 14, 'A-008', 'available'), (24, 14, 'A-009', 'available'),
(24, 14, 'A-010', 'available'), (24, 14, 'A-011', 'available'), (24, 14, 'A-012', 'available'),
(24, 14, 'A-013', 'available'), (24, 14, 'A-014', 'available'), (24, 14, 'A-015', 'available'),
(24, 14, 'A-016', 'available'), (24, 14, 'A-017', 'available'), (24, 14, 'A-018', 'available'),
(24, 14, 'A-019', 'available'), (24, 14, 'A-020', 'available'), (24, 14, 'A-021', 'available'),
(24, 14, 'A-022', 'available'), (24, 14, 'A-023', 'available'), (24, 14, 'A-024', 'available'),
(24, 14, 'A-025', 'available'), (24, 14, 'A-026', 'available'), (24, 14, 'A-027', 'available'),
(24, 14, 'A-028', 'available'), (24, 14, 'A-029', 'available'), (24, 14, 'A-030', 'available'),
(24, 14, 'A-031', 'available'), (24, 14, 'A-032', 'available'), (24, 14, 'A-033', 'available'),
(24, 14, 'A-034', 'available'), (24, 14, 'A-035', 'available'), (24, 14, 'A-036', 'available'),
(24, 14, 'A-037', 'available'), (24, 14, 'A-038', 'available'), (24, 14, 'A-039', 'available'),
(24, 14, 'A-040', 'available'), (24, 14, 'A-041', 'available'), (24, 14, 'A-042', 'available'),
(24, 14, 'A-043', 'available'), (24, 14, 'A-044', 'available'), (24, 14, 'A-045', 'available'),
(24, 14, 'A-046', 'available'), (24, 14, 'A-047', 'available'), (24, 14, 'A-048', 'available'),
(24, 14, 'A-049', 'available'), (24, 14, 'A-050', 'available');

-- CAT2 section (section_id=15)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(24, 15, 'B-001', 'available'), (24, 15, 'B-002', 'available'), (24, 15, 'B-003', 'available'),
(24, 15, 'B-004', 'available'), (24, 15, 'B-005', 'available'), (24, 15, 'B-006', 'available'),
(24, 15, 'B-007', 'available'), (24, 15, 'B-008', 'available'), (24, 15, 'B-009', 'available'),
(24, 15, 'B-010', 'available'), (24, 15, 'B-011', 'available'), (24, 15, 'B-012', 'available'),
(24, 15, 'B-013', 'available'), (24, 15, 'B-014', 'available'), (24, 15, 'B-015', 'available'),
(24, 15, 'B-016', 'available'), (24, 15, 'B-017', 'available'), (24, 15, 'B-018', 'available'),
(24, 15, 'B-019', 'available'), (24, 15, 'B-020', 'available'), (24, 15, 'B-021', 'available'),
(24, 15, 'B-022', 'available'), (24, 15, 'B-023', 'available'), (24, 15, 'B-024', 'available'),
(24, 15, 'B-025', 'available'), (24, 15, 'B-026', 'available'), (24, 15, 'B-027', 'available'),
(24, 15, 'B-028', 'available'), (24, 15, 'B-029', 'available'), (24, 15, 'B-030', 'available'),
(24, 15, 'B-031', 'available'), (24, 15, 'B-032', 'available'), (24, 15, 'B-033', 'available'),
(24, 15, 'B-034', 'available'), (24, 15, 'B-035', 'available'), (24, 15, 'B-036', 'available'),
(24, 15, 'B-037', 'available'), (24, 15, 'B-038', 'available'), (24, 15, 'B-039', 'available'),
(24, 15, 'B-040', 'available'), (24, 15, 'B-041', 'available'), (24, 15, 'B-042', 'available'),
(24, 15, 'B-043', 'available'), (24, 15, 'B-044', 'available'), (24, 15, 'B-045', 'available'),
(24, 15, 'B-046', 'available'), (24, 15, 'B-047', 'available'), (24, 15, 'B-048', 'available'),
(24, 15, 'B-049', 'available'), (24, 15, 'B-050', 'available');

-- ============================================
-- Event 6: Singapore Grand Prix (event_id=25)
-- ============================================
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(25, 'VIP', 588.00, 20, 20),
(25, 'CAT1', 348.00, 40, 40),
(25, 'CAT2', 148.00, 40, 40);

-- VIP section (section_id=16)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(25, 16, 'VIP-001', 'available'), (25, 16, 'VIP-002', 'available'), (25, 16, 'VIP-003', 'available'),
(25, 16, 'VIP-004', 'available'), (25, 16, 'VIP-005', 'available'), (25, 16, 'VIP-006', 'available'),
(25, 16, 'VIP-007', 'available'), (25, 16, 'VIP-008', 'available'), (25, 16, 'VIP-009', 'available'),
(25, 16, 'VIP-010', 'available'), (25, 16, 'VIP-011', 'available'), (25, 16, 'VIP-012', 'available'),
(25, 16, 'VIP-013', 'available'), (25, 16, 'VIP-014', 'available'), (25, 16, 'VIP-015', 'available'),
(25, 16, 'VIP-016', 'available'), (25, 16, 'VIP-017', 'available'), (25, 16, 'VIP-018', 'available'),
(25, 16, 'VIP-019', 'available'), (25, 16, 'VIP-020', 'available');

-- CAT1 section (section_id=17)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(25, 17, 'A-001', 'available'), (25, 17, 'A-002', 'available'), (25, 17, 'A-003', 'available'),
(25, 17, 'A-004', 'available'), (25, 17, 'A-005', 'available'), (25, 17, 'A-006', 'available'),
(25, 17, 'A-007', 'available'), (25, 17, 'A-008', 'available'), (25, 17, 'A-009', 'available'),
(25, 17, 'A-010', 'available'), (25, 17, 'A-011', 'available'), (25, 17, 'A-012', 'available'),
(25, 17, 'A-013', 'available'), (25, 17, 'A-014', 'available'), (25, 17, 'A-015', 'available'),
(25, 17, 'A-016', 'available'), (25, 17, 'A-017', 'available'), (25, 17, 'A-018', 'available'),
(25, 17, 'A-019', 'available'), (25, 17, 'A-020', 'available'), (25, 17, 'A-021', 'available'),
(25, 17, 'A-022', 'available'), (25, 17, 'A-023', 'available'), (25, 17, 'A-024', 'available'),
(25, 17, 'A-025', 'available'), (25, 17, 'A-026', 'available'), (25, 17, 'A-027', 'available'),
(25, 17, 'A-028', 'available'), (25, 17, 'A-029', 'available'), (25, 17, 'A-030', 'available'),
(25, 17, 'A-031', 'available'), (25, 17, 'A-032', 'available'), (25, 17, 'A-033', 'available'),
(25, 17, 'A-034', 'available'), (25, 17, 'A-035', 'available'), (25, 17, 'A-036', 'available'),
(25, 17, 'A-037', 'available'), (25, 17, 'A-038', 'available'), (25, 17, 'A-039', 'available'),
(25, 17, 'A-040', 'available');

-- CAT2 section (section_id=18)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(25, 18, 'B-001', 'available'), (25, 18, 'B-002', 'available'), (25, 18, 'B-003', 'available'),
(25, 18, 'B-004', 'available'), (25, 18, 'B-005', 'available'), (25, 18, 'B-006', 'available'),
(25, 18, 'B-007', 'available'), (25, 18, 'B-008', 'available'), (25, 18, 'B-009', 'available'),
(25, 18, 'B-010', 'available'), (25, 18, 'B-011', 'available'), (25, 18, 'B-012', 'available'),
(25, 18, 'B-013', 'available'), (25, 18, 'B-014', 'available'), (25, 18, 'B-015', 'available'),
(25, 18, 'B-016', 'available'), (25, 18, 'B-017', 'available'), (25, 18, 'B-018', 'available'),
(25, 18, 'B-019', 'available'), (25, 18, 'B-020', 'available'), (25, 18, 'B-021', 'available'),
(25, 18, 'B-022', 'available'), (25, 18, 'B-023', 'available'), (25, 18, 'B-024', 'available'),
(25, 18, 'B-025', 'available'), (25, 18, 'B-026', 'available'), (25, 18, 'B-027', 'available'),
(25, 18, 'B-028', 'available'), (25, 18, 'B-029', 'available'), (25, 18, 'B-030', 'available'),
(25, 18, 'B-031', 'available'), (25, 18, 'B-032', 'available'), (25, 18, 'B-033', 'available'),
(25, 18, 'B-034', 'available'), (25, 18, 'B-035', 'available'), (25, 18, 'B-036', 'available'),
(25, 18, 'B-037', 'available'), (25, 18, 'B-038', 'available'), (25, 18, 'B-039', 'available'),
(25, 18, 'B-040', 'available');

-- ============================================
-- Event 7: Phantom of the Opera (event_id=26)
-- ============================================
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(26, 'VIP', 258.00, 20, 20),
(26, 'CAT1', 168.00, 30, 30),
(26, 'CAT2', 68.00, 30, 30);

-- VIP section (section_id=19)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(26, 19, 'VIP-001', 'available'), (26, 19, 'VIP-002', 'available'), (26, 19, 'VIP-003', 'available'),
(26, 19, 'VIP-004', 'available'), (26, 19, 'VIP-005', 'available'), (26, 19, 'VIP-006', 'available'),
(26, 19, 'VIP-007', 'available'), (26, 19, 'VIP-008', 'available'), (26, 19, 'VIP-009', 'available'),
(26, 19, 'VIP-010', 'available'), (26, 19, 'VIP-011', 'available'), (26, 19, 'VIP-012', 'available'),
(26, 19, 'VIP-013', 'available'), (26, 19, 'VIP-014', 'available'), (26, 19, 'VIP-015', 'available'),
(26, 19, 'VIP-016', 'available'), (26, 19, 'VIP-017', 'available'), (26, 19, 'VIP-018', 'available'),
(26, 19, 'VIP-019', 'available'), (26, 19, 'VIP-020', 'available');

-- CAT1 section (section_id=20)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(26, 20, 'A-001', 'available'), (26, 20, 'A-002', 'available'), (26, 20, 'A-003', 'available'),
(26, 20, 'A-004', 'available'), (26, 20, 'A-005', 'available'), (26, 20, 'A-006', 'available'),
(26, 20, 'A-007', 'available'), (26, 20, 'A-008', 'available'), (26, 20, 'A-009', 'available'),
(26, 20, 'A-010', 'available'), (26, 20, 'A-011', 'available'), (26, 20, 'A-012', 'available'),
(26, 20, 'A-013', 'available'), (26, 20, 'A-014', 'available'), (26, 20, 'A-015', 'available'),
(26, 20, 'A-016', 'available'), (26, 20, 'A-017', 'available'), (26, 20, 'A-018', 'available'),
(26, 20, 'A-019', 'available'), (26, 20, 'A-020', 'available'), (26, 20, 'A-021', 'available'),
(26, 20, 'A-022', 'available'), (26, 20, 'A-023', 'available'), (26, 20, 'A-024', 'available'),
(26, 20, 'A-025', 'available'), (26, 20, 'A-026', 'available'), (26, 20, 'A-027', 'available'),
(26, 20, 'A-028', 'available'), (26, 20, 'A-029', 'available'), (26, 20, 'A-030', 'available');

-- CAT2 section (section_id=21)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(26, 21, 'B-001', 'available'), (26, 21, 'B-002', 'available'), (26, 21, 'B-003', 'available'),
(26, 21, 'B-004', 'available'), (26, 21, 'B-005', 'available'), (26, 21, 'B-006', 'available'),
(26, 21, 'B-007', 'available'), (26, 21, 'B-008', 'available'), (26, 21, 'B-009', 'available'),
(26, 21, 'B-010', 'available'), (26, 21, 'B-011', 'available'), (26, 21, 'B-012', 'available'),
(26, 21, 'B-013', 'available'), (26, 21, 'B-014', 'available'), (26, 21, 'B-015', 'available'),
(26, 21, 'B-016', 'available'), (26, 21, 'B-017', 'available'), (26, 21, 'B-018', 'available'),
(26, 21, 'B-019', 'available'), (26, 21, 'B-020', 'available'), (26, 21, 'B-021', 'available'),
(26, 21, 'B-022', 'available'), (26, 21, 'B-023', 'available'), (26, 21, 'B-024', 'available'),
(26, 21, 'B-025', 'available'), (26, 21, 'B-026', 'available'), (26, 21, 'B-027', 'available'),
(26, 21, 'B-028', 'available'), (26, 21, 'B-029', 'available'), (26, 21, 'B-030', 'available');

-- ============================================
-- Event 8: Russell Peters Comedy (event_id=27)
-- ============================================
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(27, 'VIP', 198.00, 15, 15),
(27, 'CAT1', 138.00, 25, 25),
(27, 'CAT2', 78.00, 25, 25);

-- VIP section (section_id=22)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(27, 22, 'VIP-001', 'available'), (27, 22, 'VIP-002', 'available'), (27, 22, 'VIP-003', 'available'),
(27, 22, 'VIP-004', 'available'), (27, 22, 'VIP-005', 'available'), (27, 22, 'VIP-006', 'available'),
(27, 22, 'VIP-007', 'available'), (27, 22, 'VIP-008', 'available'), (27, 22, 'VIP-009', 'available'),
(27, 22, 'VIP-010', 'available'), (27, 22, 'VIP-011', 'available'), (27, 22, 'VIP-012', 'available'),
(27, 22, 'VIP-013', 'available'), (27, 22, 'VIP-014', 'available'), (27, 22, 'VIP-015', 'available');

-- CAT1 section (section_id=23)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(27, 23, 'A-001', 'available'), (27, 23, 'A-002', 'available'), (27, 23, 'A-003', 'available'),
(27, 23, 'A-004', 'available'), (27, 23, 'A-005', 'available'), (27, 23, 'A-006', 'available'),
(27, 23, 'A-007', 'available'), (27, 23, 'A-008', 'available'), (27, 23, 'A-009', 'available'),
(27, 23, 'A-010', 'available'), (27, 23, 'A-011', 'available'), (27, 23, 'A-012', 'available'),
(27, 23, 'A-013', 'available'), (27, 23, 'A-014', 'available'), (27, 23, 'A-015', 'available'),
(27, 23, 'A-016', 'available'), (27, 23, 'A-017', 'available'), (27, 23, 'A-018', 'available'),
(27, 23, 'A-019', 'available'), (27, 23, 'A-020', 'available'), (27, 23, 'A-021', 'available'),
(27, 23, 'A-022', 'available'), (27, 23, 'A-023', 'available'), (27, 23, 'A-024', 'available'),
(27, 23, 'A-025', 'available');

-- CAT2 section (section_id=24)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(27, 24, 'B-001', 'available'), (27, 24, 'B-002', 'available'), (27, 24, 'B-003', 'available'),
(27, 24, 'B-004', 'available'), (27, 24, 'B-005', 'available'), (27, 24, 'B-006', 'available'),
(27, 24, 'B-007', 'available'), (27, 24, 'B-008', 'available'), (27, 24, 'B-009', 'available'),
(27, 24, 'B-010', 'available'), (27, 24, 'B-011', 'available'), (27, 24, 'B-012', 'available'),
(27, 24, 'B-013', 'available'), (27, 24, 'B-014', 'available'), (27, 24, 'B-015', 'available'),
(27, 24, 'B-016', 'available'), (27, 24, 'B-017', 'available'), (27, 24, 'B-018', 'available'),
(27, 24, 'B-019', 'available'), (27, 24, 'B-020', 'available'), (27, 24, 'B-021', 'available'),
(27, 24, 'B-022', 'available'), (27, 24, 'B-023', 'available'), (27, 24, 'B-024', 'available'),
(27, 24, 'B-025', 'available');

-- ============================================
-- Event 9: Singapore Jazz Festival (event_id=28)
-- ============================================
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(28, 'VIP', 288.00, 20, 20),
(28, 'CAT1', 188.00, 40, 40),
(28, 'CAT2', 88.00, 40, 40);

-- VIP section (section_id=25)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(28, 25, 'VIP-001', 'available'), (28, 25, 'VIP-002', 'available'), (28, 25, 'VIP-003', 'available'),
(28, 25, 'VIP-004', 'available'), (28, 25, 'VIP-005', 'available'), (28, 25, 'VIP-006', 'available'),
(28, 25, 'VIP-007', 'available'), (28, 25, 'VIP-008', 'available'), (28, 25, 'VIP-009', 'available'),
(28, 25, 'VIP-010', 'available'), (28, 25, 'VIP-011', 'available'), (28, 25, 'VIP-012', 'available'),
(28, 25, 'VIP-013', 'available'), (28, 25, 'VIP-014', 'available'), (28, 25, 'VIP-015', 'available'),
(28, 25, 'VIP-016', 'available'), (28, 25, 'VIP-017', 'available'), (28, 25, 'VIP-018', 'available'),
(28, 25, 'VIP-019', 'available'), (28, 25, 'VIP-020', 'available');

-- CAT1 section (section_id=26)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(28, 26, 'A-001', 'available'), (28, 26, 'A-002', 'available'), (28, 26, 'A-003', 'available'),
(28, 26, 'A-004', 'available'), (28, 26, 'A-005', 'available'), (28, 26, 'A-006', 'available'),
(28, 26, 'A-007', 'available'), (28, 26, 'A-008', 'available'), (28, 26, 'A-009', 'available'),
(28, 26, 'A-010', 'available'), (28, 26, 'A-011', 'available'), (28, 26, 'A-012', 'available'),
(28, 26, 'A-013', 'available'), (28, 26, 'A-014', 'available'), (28, 26, 'A-015', 'available'),
(28, 26, 'A-016', 'available'), (28, 26, 'A-017', 'available'), (28, 26, 'A-018', 'available'),
(28, 26, 'A-019', 'available'), (28, 26, 'A-020', 'available'), (28, 26, 'A-021', 'available'),
(28, 26, 'A-022', 'available'), (28, 26, 'A-023', 'available'), (28, 26, 'A-024', 'available'),
(28, 26, 'A-025', 'available'), (28, 26, 'A-026', 'available'), (28, 26, 'A-027', 'available'),
(28, 26, 'A-028', 'available'), (28, 26, 'A-029', 'available'), (28, 26, 'A-030', 'available'),
(28, 26, 'A-031', 'available'), (28, 26, 'A-032', 'available'), (28, 26, 'A-033', 'available'),
(28, 26, 'A-034', 'available'), (28, 26, 'A-035', 'available'), (28, 26, 'A-036', 'available'),
(28, 26, 'A-037', 'available'), (28, 26, 'A-038', 'available'), (28, 26, 'A-039', 'available'),
(28, 26, 'A-040', 'available');

-- CAT2 section (section_id=27)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(28, 27, 'B-001', 'available'), (28, 27, 'B-002', 'available'), (28, 27, 'B-003', 'available'),
(28, 27, 'B-004', 'available'), (28, 27, 'B-005', 'available'), (28, 27, 'B-006', 'available'),
(28, 27, 'B-007', 'available'), (28, 27, 'B-008', 'available'), (28, 27, 'B-009', 'available'),
(28, 27, 'B-010', 'available'), (28, 27, 'B-011', 'available'), (28, 27, 'B-012', 'available'),
(28, 27, 'B-013', 'available'), (28, 27, 'B-014', 'available'), (28, 27, 'B-015', 'available'),
(28, 27, 'B-016', 'available'), (28, 27, 'B-017', 'available'), (28, 27, 'B-018', 'available'),
(28, 27, 'B-019', 'available'), (28, 27, 'B-020', 'available'), (28, 27, 'B-021', 'available'),
(28, 27, 'B-022', 'available'), (28, 27, 'B-023', 'available'), (28, 27, 'B-024', 'available'),
(28, 27, 'B-025', 'available'), (28, 27, 'B-026', 'available'), (28, 27, 'B-027', 'available'),
(28, 27, 'B-028', 'available'), (28, 27, 'B-029', 'available'), (28, 27, 'B-030', 'available'),
(28, 27, 'B-031', 'available'), (28, 27, 'B-032', 'available'), (28, 27, 'B-033', 'available'),
(28, 27, 'B-034', 'available'), (28, 27, 'B-035', 'available'), (28, 27, 'B-036', 'available'),
(28, 27, 'B-037', 'available'), (28, 27, 'B-038', 'available'), (28, 27, 'B-039', 'available'),
(28, 27, 'B-040', 'available');

-- ============================================
-- Event 10: Bruno Mars (event_id=29)
-- ============================================
INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES
(29, 'VIP', 398.00, 25, 25),
(29, 'CAT1', 258.00, 50, 50),
(29, 'CAT2', 108.00, 50, 50);

-- VIP section (section_id=28)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(29, 28, 'VIP-001', 'available'), (29, 28, 'VIP-002', 'available'), (29, 28, 'VIP-003', 'available'),
(29, 28, 'VIP-004', 'available'), (29, 28, 'VIP-005', 'available'), (29, 28, 'VIP-006', 'available'),
(29, 28, 'VIP-007', 'available'), (29, 28, 'VIP-008', 'available'), (29, 28, 'VIP-009', 'available'),
(29, 28, 'VIP-010', 'available'), (29, 28, 'VIP-011', 'available'), (29, 28, 'VIP-012', 'available'),
(29, 28, 'VIP-013', 'available'), (29, 28, 'VIP-014', 'available'), (29, 28, 'VIP-015', 'available'),
(29, 28, 'VIP-016', 'available'), (29, 28, 'VIP-017', 'available'), (29, 28, 'VIP-018', 'available'),
(29, 28, 'VIP-019', 'available'), (29, 28, 'VIP-020', 'available'), (29, 28, 'VIP-021', 'available'),
(29, 28, 'VIP-022', 'available'), (29, 28, 'VIP-023', 'available'), (29, 28, 'VIP-024', 'available'),
(29, 28, 'VIP-025', 'available');

-- CAT1 section (section_id=29)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(29, 29, 'A-001', 'available'), (29, 29, 'A-002', 'available'), (29, 29, 'A-003', 'available'),
(29, 29, 'A-004', 'available'), (29, 29, 'A-005', 'available'), (29, 29, 'A-006', 'available'),
(29, 29, 'A-007', 'available'), (29, 29, 'A-008', 'available'), (29, 29, 'A-009', 'available'),
(29, 29, 'A-010', 'available'), (29, 29, 'A-011', 'available'), (29, 29, 'A-012', 'available'),
(29, 29, 'A-013', 'available'), (29, 29, 'A-014', 'available'), (29, 29, 'A-015', 'available'),
(29, 29, 'A-016', 'available'), (29, 29, 'A-017', 'available'), (29, 29, 'A-018', 'available'),
(29, 29, 'A-019', 'available'), (29, 29, 'A-020', 'available'), (29, 29, 'A-021', 'available'),
(29, 29, 'A-022', 'available'), (29, 29, 'A-023', 'available'), (29, 29, 'A-024', 'available'),
(29, 29, 'A-025', 'available'), (29, 29, 'A-026', 'available'), (29, 29, 'A-027', 'available'),
(29, 29, 'A-028', 'available'), (29, 29, 'A-029', 'available'), (29, 29, 'A-030', 'available'),
(29, 29, 'A-031', 'available'), (29, 29, 'A-032', 'available'), (29, 29, 'A-033', 'available'),
(29, 29, 'A-034', 'available'), (29, 29, 'A-035', 'available'), (29, 29, 'A-036', 'available'),
(29, 29, 'A-037', 'available'), (29, 29, 'A-038', 'available'), (29, 29, 'A-039', 'available'),
(29, 29, 'A-040', 'available'), (29, 29, 'A-041', 'available'), (29, 29, 'A-042', 'available'),
(29, 29, 'A-043', 'available'), (29, 29, 'A-044', 'available'), (29, 29, 'A-045', 'available'),
(29, 29, 'A-046', 'available'), (29, 29, 'A-047', 'available'), (29, 29, 'A-048', 'available'),
(29, 29, 'A-049', 'available'), (29, 29, 'A-050', 'available');

-- CAT2 section (section_id=30)
INSERT INTO seats (event_id, section_id, seat_number, status) VALUES
(29, 30, 'B-001', 'available'), (29, 30, 'B-002', 'available'), (29, 30, 'B-003', 'available'),
(29, 30, 'B-004', 'available'), (29, 30, 'B-005', 'available'), (29, 30, 'B-006', 'available'),
(29, 30, 'B-007', 'available'), (29, 30, 'B-008', 'available'), (29, 30, 'B-009', 'available'),
(29, 30, 'B-010', 'available'), (29, 30, 'B-011', 'available'), (29, 30, 'B-012', 'available'),
(29, 30, 'B-013', 'available'), (29, 30, 'B-014', 'available'), (29, 30, 'B-015', 'available'),
(29, 30, 'B-016', 'available'), (29, 30, 'B-017', 'available'), (29, 30, 'B-018', 'available'),
(29, 30, 'B-019', 'available'), (29, 30, 'B-020', 'available'), (29, 30, 'B-021', 'available'),
(29, 30, 'B-022', 'available'), (29, 30, 'B-023', 'available'), (29, 30, 'B-024', 'available'),
(29, 30, 'B-025', 'available'), (29, 30, 'B-026', 'available'), (29, 30, 'B-027', 'available'),
(29, 30, 'B-028', 'available'), (29, 30, 'B-029', 'available'), (29, 30, 'B-030', 'available'),
(29, 30, 'B-031', 'available'), (29, 30, 'B-032', 'available'), (29, 30, 'B-033', 'available'),
(29, 30, 'B-034', 'available'), (29, 30, 'B-035', 'available'), (29, 30, 'B-036', 'available'),
(29, 30, 'B-037', 'available'), (29, 30, 'B-038', 'available'), (29, 30, 'B-039', 'available'),
(29, 30, 'B-040', 'available'), (29, 30, 'B-041', 'available'), (29, 30, 'B-042', 'available'),
(29, 30, 'B-043', 'available'), (29, 30, 'B-044', 'available'), (29, 30, 'B-045', 'available'),
(29, 30, 'B-046', 'available'), (29, 30, 'B-047', 'available'), (29, 30, 'B-048', 'available'),
(29, 30, 'B-049', 'available'), (29, 30, 'B-050', 'available');
