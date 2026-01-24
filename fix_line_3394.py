# fix_line_3394.py
print("🔧 Fixing line 3394...")

with open('quickconnect/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 3394 (index 3393 in 0-based)
line_3394 = lines[3393]

print(f"Before: {repr(line_3394)}")

# Count the indentation level - it should match line 3393
line_3393 = lines[3392]  # The logger.error line
indentation_level = len(line_3393) - len(line_3393.lstrip())

# Create proper indentation
proper_indentation = ' ' * indentation_level
lines[3393] = proper_indentation + 'return JsonResponse({\n'

print(f"After: {repr(lines[3393])}")

# Write back
with open('quickconnect/views.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Fixed line 3394")