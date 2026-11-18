"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMG_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def fix(ds, issues, cfg):
    err_issues = [i for i in issues if i.severity == ERROR]
    if not err_issues:
        return []

    fixes = []
    removed_images = set()

    # 1. Xoá ảnh không hợp lệ (trùng, rò rỉ, hỏng, kích thước nhỏ)
    for i in err_issues:
        if i.code in REMOVE_IMG_CODES and i.image not in removed_images:
            removed_images.add(i.image)
            img_p = ds.image_path(i.image)
            lbl_p = ds.label_path(i.image)
            existed = False
            if img_p is not None and img_p.exists():
                img_p.unlink()
                existed = True
            if lbl_p.exists():
                lbl_p.unlink()
                existed = True
            ds._size_cache.pop(i.image, None)
            if existed:
                fixes.append({
                    "image": i.image,
                    "line": "",
                    "action": "remove_image",
                    "before": i.code,
                    "after": "đã xoá ảnh và nhãn",
                })

    # 2. Sửa tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in err_issues):
        expected = {idx: name for idx, name in enumerate(cfg["classes"])}
        cur_names = ds.yaml_names()
        if cur_names != expected:
            data = {}
            if ds.yaml_path.exists():
                try:
                    data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = {}
            if not isinstance(data, dict):
                data = {}
            data["names"] = expected
            ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append({
                "image": "data.yaml",
                "line": "",
                "action": "rename_classes",
                "before": str(cur_names),
                "after": str(cfg["classes"]),
            })

    # 3. Ghi nhận ảnh thiếu file nhãn để chuyển người gán
    seen_missing = set()
    for i in err_issues:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed_images and i.image not in seen_missing:
            if not ds.label_path(i.image).exists():
                seen_missing.add(i.image)
                fixes.append({
                    "image": i.image,
                    "line": "",
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                })

    # 4. Gom lỗi theo từng file nhãn và xử lý một lần trên số dòng gốc
    by_file = defaultdict(lambda: defaultdict(set))
    for i in err_issues:
        if i.image in removed_images or i.line is None:
            continue
        if i.code in DROP_CODES or i.code == "BOX_OUT_OF_IMAGE":
            by_file[i.image][i.line].add(i.code)

    for stem in sorted(by_file):
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        raw_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        line_codes = by_file[stem]
        new_lines = []
        changed = False

        for idx, orig in enumerate(raw_lines, start=1):
            codes = line_codes.get(idx)
            if not codes:
                new_lines.append(orig)
                continue

            if codes & DROP_CODES:
                fixes.append({
                    "image": stem,
                    "line": idx,
                    "action": "drop_line",
                    "before": orig,
                    "after": "",
                })
                changed = True
                continue

            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    cls_id, cx, cy, w, h = parse_yolo_line(orig)
                except ValueError:
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": orig,
                        "after": "",
                    })
                    changed = True
                    continue

                x1, y1 = cx - w / 2, cy - h / 2
                x2, y2 = cx + w / 2, cy + h / 2
                nx1, ny1 = max(0.0, x1), max(0.0, y1)
                nx2, ny2 = min(1.0, x2), min(1.0, y2)
                if (nx1, ny1, nx2, ny2) == (x1, y1, x2, y2):
                    new_lines.append(orig)
                    continue
                nw = nx2 - nx1
                nh = ny2 - ny1

                if nw <= 1e-6 or nh <= 1e-6:
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": orig,
                        "after": "",
                    })
                    changed = True
                else:
                    ncx = (nx1 + nx2) / 2
                    ncy = (ny1 + ny2) / 2
                    after_line = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                    new_lines.append(after_line)
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "clip_box",
                        "before": orig,
                        "after": after_line,
                    })
                    changed = True
            else:
                new_lines.append(orig)

        if changed:
            lbl_p.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

    return fixes
