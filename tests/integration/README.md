# Integration Test Suite

## Purpose

Test complete player workflows end-to-end, not just individual components.

**Unit tests** verify that `can_see_character()` works.  
**Integration tests** verify that `look hassan` actually calls it.

## Default behaviour: SKIPPED

**These tests do not run under `pytest` or `make test`.** They were originally
a "ROM 2.4 port completion" parity harness — tests that lock the Python port
to ROM C source line-by-line. The project no longer treats ROM parity as a
goal (the previous authors were obsessed with absolute parity with the
legacy code, but we are not), so the 2987-test suite is preserved for
reference but skipped by default.

The skip is implemented in `tests/conftest.py` (top-level) and gates on
the `--include-parity` CLI option. The default `pytest` and `make test`
run ~1700 non-parity tests; the parity suite is opt-in.

## Running the parity tests

```bash
# All integration tests (opt-in, ~4 min)
pytest --include-parity
# or
make test-parity

# Just one file
pytest tests/integration/test_player_npc_interaction.py --include-parity -v

# Filter to specific markers
pytest tests/integration/ --include-parity -m "not skip"
```

## Running tests (other)

```bash
# Run all integration tests (requires --include-parity, see above)
pytest tests/integration/ -v

# Run only passing tests (skip unimplemented features)
pytest tests/integration/ -v -m "not skip"

# Run specific workflow
pytest tests/integration/test_player_npc_interaction.py -v

# Run with coverage
pytest tests/integration/ --cov=mud.commands --cov-report=term
```

## Test Organization

### test_player_npc_interaction.py
Tests basic NPC interactions:
- Looking at NPCs
- Considering mob difficulty
- Following NPCs
- Giving items
- Communication

### test_new_player_workflow.py
End-to-end simulation of new player's first 30 minutes

### test_shop_workflow.py (TODO)
Complete shop interaction tests

### test_combat_workflow.py (TODO)
Combat scenario tests

## Current Status

As of 2025-12-22:

**Passing**: 2 tests (current limitation documentation)
**Skipped**: 15 tests (waiting for P0 command implementation)
**Failing**: 0 tests

## Progress Tracking

Use these tests to track implementation progress:

### Phase 1: Basic Interaction
- [ ] test_player_can_look_at_mob
- [ ] test_player_can_consider_mob
- [ ] test_player_can_give_item_to_mob
- [ ] test_tell_to_mob

### Phase 2: Group Mechanics
- [ ] test_player_can_follow_mob
- [ ] test_player_follows_then_groups
- [ ] test_grouped_player_moves_with_leader

### Phase 3: Commerce
- [ ] test_player_can_list_shop_inventory
- [ ] test_complete_purchase_workflow

### Phase 4: Combat
- [ ] test_consider_before_combat
- [ ] test_flee_from_combat

## When a Test Fails

Integration test failures indicate:
1. Command not implemented (marked with @pytest.mark.skip)
2. Command implemented but broken
3. Regression in existing functionality

**Always run integration tests after:**
- Implementing a new command
- Modifying command dispatcher
- Changing core game mechanics

## Writing New Tests

```python
def test_my_workflow(test_player, test_mob):
    """Test description"""
    # Arrange - set up the scenario
    # Act - execute commands
    result = process_command(test_player, "command args")
    # Assert - verify results
    assert expected in result.lower()
```

## Success Criteria

✅ **Phase 1 Complete** when:
- All TestPlayerMeetsNPC tests pass
- test_shopkeeper_interaction_workflow passes

✅ **Phase 2 Complete** when:
- All TestGroupFormation tests pass
- test_group_quest_workflow passes

✅ **"Gameplay Parity"** when:
- test_complete_new_player_experience passes
- New player can play for 30 minutes without "Huh?"
