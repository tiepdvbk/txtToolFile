# TextFile

Ứng dụng Windows gộp và tách văn bản. Chỉ cần chọn **thư mục gốc của truyện**; nguồn, file tổng hợp và thư mục kết quả được thiết lập tự động.

## Sử dụng

1. Mở `dist\TextFileTool-v2.exe` hoặc nhấp đôi `run.bat` để chạy mã nguồn.
2. Chọn hoặc dán thư mục gốc, ví dụ `C:\PIUPIU\ten-truyen`. Không cần chọn từng thư mục con.
3. Bấm **Gộp & tách ngay**. Có thể chọn **Chỉ gộp file** hoặc **Chỉ tách file** trong menu bên trái.

Nếu tải mã nguồn từ GitHub, chạy `run.bat` hoặc dùng `build.bat` để tạo EXE trước. Ứng dụng dùng thiết lập mặc định khi chưa có `config.json` và tự tạo cấu hình khi lưu. `config.example.json` là cấu hình mẫu; cấu hình cá nhân, môi trường Python và thư mục build không được đưa vào Git.

Ví dụ cấu trúc:

```text
ten-truyen/
  raw/           Các chương nguyên liệu
  raw_tach/      Các chương nguyên liệu đã xử lý
  v1/            Các file chương cần gộp
    1-2.txt
    3-4.txt
    all.txt      Tự tạo khi gộp
  v2/            Tự nhận hoặc tự tạo khi lưu kết quả
    1.txt
    2.txt
```

Luồng mặc định: **v1 → v1/all.txt → v2/1.txt, 2.txt…**

- Tự nhận tên thư mục không phân biệt hoa thường, kể cả `V1`, `V2`, `RAW`.
- Ưu tiên nguồn có file chương theo thứ tự `v1`, `raw`, `raw_tach` khi chưa có lựa chọn được lưu. Nếu đã chọn nguồn, ứng dụng giữ lựa chọn đó khi thư mục này có mặt.
- Có thể đổi nguồn bằng ô **Nguồn** ngay trên các thẻ đường dẫn. Chọn `raw` thì file tổng hợp là `raw/all.txt`; các phần vẫn được lưu trong `v2`.
- Nếu các file chương nằm ngay trong gốc truyện, nguồn `.` cũng được nhận diện.
- `v2` dùng làm đích. Các thư mục sao lưu và thư mục con khác không được gộp chung vào nguồn.
- Thẻ đường dẫn hiển thị số file nguồn, tên đầu/cuối và tình trạng file tổng hợp, thư mục kết quả. Bấm **Quét lại** sau khi thêm/bớt file bên ngoài.
- **Chỉ tách file** dùng `all.txt` có sẵn trong nguồn đang chọn. Nếu chưa có, dùng **Gộp & tách**.
- Phím tắt: **Ctrl+O** chọn thư mục, **Ctrl+Enter** chạy tác vụ.

## Tùy chỉnh

Ngưỡng ký tự và điểm ngắt nằm ngay trên màn hình chính. Nút **Tùy chỉnh** chứa các thiết lập khác:

- **Ngăn cách khi gộp**: một dòng mới, một dòng trống hoặc không thêm. Mặc định một dòng trống.
- **Ký tự mỗi phần**: mặc định 285000, tính theo ký tự Python, không phải byte hay token.
- **Đánh số phần từ**: mặc định 1, đầu ra `1.txt`, `2.txt`…
- **Sau dấu kết thúc câu**: đạt ngưỡng rồi tìm dấu câu tiếp theo; một phần có thể dài hơn ngưỡng. Nếu không có dấu câu tiếp theo, giữ phần còn lại.
- **Giới hạn cứng**: ưu tiên dấu câu cuối trong ngưỡng; nếu không có thì cắt đúng số ký tự, có thể ngắt giữa từ/câu.
- **Ký tự cần xóa**: mặc định xóa `"`, `*`, `>`, `“`, `”` khi tách; để trống để giữ nguyên. File tổng hợp giữ nội dung trước làm sạch.
- **Dấu kết thúc câu**: mặc định `.!?。！？`, là quy tắc theo ký tự.
- **Mã hóa file chương**: mặc định `utf-8-sig`, đọc UTF-8 có/không BOM. Hỗ trợ UTF-16, CP1258 hoặc nhập encoding khác. File `all.txt` và các phần luôn là UTF-8; bước tách đọc `all.txt` bằng UTF-8.

Chỉ nhận `.txt` có tên số nguyên không âm hoặc khoảng chương, ví dụ `1.txt`, `10.txt`, `1-3.txt`, `4-6.txt`. Sắp theo số đầu, số cuối, rồi tên file; không duyệt sâu thư mục con. Không kiểm tra nội dung chương để phát hiện thiếu/trùng chương.

## Lưu cấu hình và kết quả

Ứng dụng lưu `config.json` cạnh mã nguồn/EXE khi chạy, đóng ứng dụng hoặc lưu tùy chỉnh. Cấu hình cũ dùng bốn đường dẫn được chuyển sang thư mục gốc tự động, giữ các tùy chỉnh xử lý và ghi đè. `root_folder` và `source_folder` là hai trường xác định đường dẫn; các đích được tính lại mỗi lần chọn gốc.

Mặc định không ghi đè. Khi bật **Ghi đè file trùng tên**, chỉ thay file đầu ra trùng tên. Các phần cũ có số lớn hơn kết quả mới, file âm thanh và file khác vẫn được giữ lại.

**Gộp & tách** chuẩn bị cả hai bước trong thư mục tạm trước khi lưu. Lỗi mã hóa, lỗi tách hoặc xung đột file sẽ hủy kết quả tạm trước khi công bố. Không chỉnh sửa các file chương nguồn. Bước công bố gồm nhiều lần di chuyển file; lỗi ổ đĩa giữa chừng vẫn có thể để lại một phần kết quả. Chức năng tách đọc toàn bộ văn bản vào RAM.

## Chạy từ mã nguồn và build

Cần Python 3.10+ có Tkinter; không cần thư viện ngoài để chạy mã nguồn.

- `run.bat`: chạy ứng dụng.
- `build.bat`: cài PyInstaller vào `.venv` rồi tạo lại **`dist\TextFileTool-v2.exe`**, giữ tên EXE hiện có để các shortcut tiếp tục dùng được. Lần đầu cần internet để cài PyInstaller.
- Có thể chép EXE sang máy Windows khác không có Python. Chép kèm `config.json` nếu muốn mang theo cấu hình; đặt tại thư mục có quyền ghi.

## Cấu trúc và kiểm tra

- `app.py`: giao diện, cấu hình, xử lý nền.
- `src/project.py`: nhận diện gốc truyện, suy ra đường dẫn, chạy gộp/tách liên tiếp.
- `src/merge.py`: nhận diện chương, sắp thứ tự và gộp.
- `src/split.py`: làm sạch và tách văn bản.
- `tests/`: thứ tự chương, bảo toàn nội dung, nhận diện đường dẫn, mã hóa và bảo vệ file khi trùng đích.

Chạy: `python -m unittest discover -s tests -v`.
