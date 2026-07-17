# Validation Scripts

Automated tools for validating QuickMUD functionality and ROM C parity.

## 🛠️ Scripts

### validate_area_parity.py
Validates area file ROM C compatibility.

**Usage**:
```bash
# Validate area file
python3 scripts/validation/validate_area_parity.py area/midgaard.are
```

## 📊 Output

Validation scripts provide:
- Summary statistics (total mobs, programs, errors)
- Detailed error messages with line numbers
- Warning messages for suspicious patterns

## 🔗 Related

- **Tests**: See [tests/integration/](../../tests/integration/)

## ✅ Status

All validation scripts operational and tested.
