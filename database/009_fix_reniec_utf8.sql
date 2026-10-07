-- BancoCloud migration 009
-- Repairs UTF-8 synthetic RENIEC names using ASCII-safe hex literals.
-- Keeps historical identity verifications unchanged.

BEGIN;

UPDATE reniec_simulated_registry
SET full_name = convert_from(
    decode(
        '4d6174656f2052616dc3ad72657a2053616c617a6172',
        'hex'
    ),
    'UTF8'
)
WHERE document_number = '70000001';

UPDATE reniec_simulated_registry
SET full_name = convert_from(
    decode(
        '416e61204c7563c3ad6120546f7272657320526f6a6173',
        'hex'
    ),
    'UTF8'
)
WHERE document_number = '70000002';

UPDATE reniec_simulated_registry
SET full_name = convert_from(
    decode(
        '4361726c6f7320416e6472c3a973204d656e646f7a612050617265646573',
        'hex'
    ),
    'UTF8'
)
WHERE document_number = '70000003';

UPDATE reniec_simulated_registry
SET full_name = convert_from(
    decode(
        '4c7563c3ad61204665726e616e6461205665676120536f746f',
        'hex'
    ),
    'UTF8'
)
WHERE document_number = '70000004';

COMMIT;
