# Review: RELEASE-PRACTICAL-POLISH-V1

## Summary

Added practical user-facing guidance to README.md and enriched the release checklist with LibreOffice compatibility items and a release test record template. No source files, build scripts, or runtime behavior were modified.

## Changed Files

- `README.md` — enhanced LibreOffice section, troubleshooting subsection, large folder note, release test expectations, 4 new FAQ entries
- `docs/94-release-checklist-v1.md` — added LibreOffice compatibility checklist items and release test record template (unnumbered section)
- `reports/reviews/release_practical_polish_v1_review.md` — this report

## README Improvements

### LibreOffice Section
- Added Windows version compatibility note (LibreOffice newer versions require Windows 10+)
- Cautionary wording: "较新版" / "较旧版" — no exact version claims
- Added note: change env vars requires app restart
- Added note: PDF/images/Markdown/Text do NOT depend on LibreOffice

### Office Preview Troubleshooting Subsection
- 6-step checklist for Office preview failures:
  1. Not installed?
  2. Windows version incompatible?
  3. Path wrong?
  4. First conversion slow?
  5. File damaged/encrypted?
  6. Stale cache?
- Clear statement that non-Office formats don't depend on LibreOffice

### Large Folder Note
- Added under usage flow: first load of large folders is slower
- Recommends starting with smaller folder for first verification
- Future optimization noted as possible but no delivery date promised

### Release Test Expectations
- Added note near release zip section: test outside repository (`D:\tmp\`)
- 5 key verification points listed (no terminal, browser opens, tray, browser-close doesn't exit, tray exit fully stops)

### FAQ Additions
- Q: LibreOffice install requires Windows 10+ → use older LO or Win10+ machine
- Q: Can use without LibreOffice? → Yes, PDF/images/MD/text work
- Q: Why slow on first large folder? → tree scan + index + prewarm; use smaller folder first
- Q: Where to test release zip? → outside repo (`D:\tmp\`), not inside `dist/`/`build/`/`release_packages/`

## Checklist Improvements

### LibreOffice Compatibility Items (Section 8, subsection)
```
[ ] 记录测试机 Windows 版本
[ ] LibreOffice 安装版本与 Windows 版本兼容
[ ] soffice.exe 路径可定位
[ ] 未安装 LibreOffice 时，PDF/图片/Markdown/Text 仍可正常预览
[ ] 未安装或不可用 LibreOffice 时，Office 预览错误提示友好
```

### Release Test Record Template (unnumbered section, before Section 12)
```
test_date:
tester:
windows_version:
python_version:
libreoffice_installed: yes/no
libreoffice_path:
package_name:
extract_path:
result: PASS/FAIL
notes:
```

## Validation

| Check | Status |
|-------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| README content: Office 预览失败/Win10/SOFFICE/LIBREOFFICE_HOME/大目录/发布 zip/关闭浏览器 | PASS |
| Checklist content: Windows 版本/LibreOffice/soffice.exe/发布实测记录/test_date/windows_version/extract_path/result: PASS/FAIL | PASS |
| Changed files scope | README.md + docs/94 + review |
| No source files changed | PASS |
| No build scripts changed | PASS |
| No static/frontend changed | PASS |
| No runtime behavior changed | PASS |
| No generated artifacts added | PASS |

## Forbidden Changes Review

| File/Area | Changed? |
|-----------|---------|
| `server.py` | No |
| `app_metadata.py` | No |
| `converter.py` | No |
| `search.py` | No |
| `annotations.py` | No |
| `tray_controller.py` | No |
| `ai/` | No |
| `scripts/` | No |
| `static/` | No |
| `requirements.txt` | No |
| `app_data/` | No |
| `dist/`/`build/`/`release_packages/` | No |

No source files changed: PASS
No build scripts changed: PASS
No frontend files changed: PASS
No runtime behavior changed: PASS

## Decision

**PASS**

All acceptance criteria met:
- Only allowed files (README.md, docs/94, review) changed
- README includes practical LibreOffice compatibility and troubleshooting guidance
- Release checklist includes practical LibreOffice compatibility check items and release test record template
- Review report exists with all required declarations
- Validation commands pass
- Commit pushed to `origin/main`
