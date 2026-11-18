"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems_set = set(image_stems)
    reviewed_set = set(reviewed or ())
    hold_thresh = cfg["gate"]["warn_ratio_hold"]

    n_errors = sum(1 for i in issues if i.severity == ERROR)
    warn_images = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in stems_set and i.image not in reviewed_set
    }
    n_warn_images = len(warn_images)
    n_images = len(stems_set)
    raw_ratio = (n_warn_images / n_images) if n_images > 0 else 0.0
    warn_ratio = round(raw_ratio, 4)

    reasons = []
    if n_errors > 0:
        decision = "Rework"
        reasons.append(f"còn {n_errors} lỗi bắt buộc chưa được xử lý")
    elif round(raw_ratio, 9) >= hold_thresh:
        decision = "Hold"
        reasons.append(
            f"tỉ lệ ảnh còn cảnh báo chưa duyệt là {n_warn_images}/{n_images} ({warn_ratio:.1%}) >= ngưỡng {hold_thresh:.0%}"
        )
    else:
        decision = "Release"
        reasons.append(
            f"0 lỗi bắt buộc, tỉ lệ ảnh cảnh báo chưa duyệt {n_warn_images}/{n_images} ({warn_ratio:.1%}) < ngưỡng {hold_thresh:.0%}"
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
