-- Script để fix timezone "Asia/Saigon" thành "Asia/Ho_Chi_Minh"
-- Chạy script này trong psql để fix lỗi timezone khi xem đồ thị

-- 1. Update timezone cho tất cả user có timezone "Asia/Saigon"
UPDATE res_users 
SET tz = 'Asia/Ho_Chi_Minh' 
WHERE tz = 'Asia/Saigon';

-- 2. Update timezone cho company nếu có
UPDATE res_company 
SET tz = 'Asia/Ho_Chi_Minh' 
WHERE tz = 'Asia/Saigon';

-- 3. Update timezone cho resource calendar nếu có
UPDATE resource_calendar 
SET tz = 'Asia/Ho_Chi_Minh' 
WHERE tz = 'Asia/Saigon';

-- 4. Kiểm tra xem còn record nào dùng "Asia/Saigon" không
SELECT 'res_users' as table_name, COUNT(*) as count 
FROM res_users WHERE tz = 'Asia/Saigon'
UNION ALL
SELECT 'res_company', COUNT(*) FROM res_company WHERE tz = 'Asia/Saigon'
UNION ALL
SELECT 'resource_calendar', COUNT(*) FROM resource_calendar WHERE tz = 'Asia/Saigon';

