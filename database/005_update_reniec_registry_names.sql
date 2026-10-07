-- BancoCloud
-- Actualización de identidades del registro RENIEC Simulator.

UPDATE reniec_simulated_registry
SET
    full_name = 'Mateo Ramírez Salazar',
    birth_date = DATE '2001-05-14',
    document_status = 'CURRENT',
    ubigeo = '150101'
WHERE document_number = '70000001';


UPDATE reniec_simulated_registry
SET
    full_name = 'Ana Lucía Torres Rojas',
    birth_date = DATE '1998-11-08',
    document_status = 'CURRENT',
    ubigeo = '150122'
WHERE document_number = '70000002';


UPDATE reniec_simulated_registry
SET
    full_name = 'Carlos Andrés Mendoza Paredes',
    birth_date = DATE '1995-03-21',
    document_status = 'NOT_CURRENT',
    ubigeo = '040101'
WHERE document_number = '70000003';


UPDATE reniec_simulated_registry
SET
    full_name = 'Lucía Fernanda Vega Soto',
    birth_date = DATE '2000-07-17',
    document_status = 'CURRENT',
    ubigeo = '130101'
WHERE document_number = '70000004';