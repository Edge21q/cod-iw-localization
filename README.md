
# COD IW Localization Tool

Bu Python aracı, Call of Duty: Infinite Warfare oyununda gerçek zamanlı bellek analizi yaparak altyazıları İngilizceden Türkçeye çevirmeye yarar. Pymem ve Facebook NLLB-200 yapay zeka modeli ile entegre çalışır.

## Özellikler
🤖 İki Çeviri Modu  
- AI Model + Cache: GPU destekli NLLB-200 modeli ile yeni metinleri çevirir  
- Cache Only: Sadece önceden çevrilmiş metinleri kullanır (hızlı, düşük kaynak)  

🚀 Gelişmiş Özellikler  
- Canlı Çeviri: Gerçek zamanlı bellek taraması ve çeviri  
- GPU Hızlandırma: CUDA destekli yapay zeka çevirisi  
- Akıllı Önbellek: Çeviri cache'i ve reverse lookup  
- Karakter İsmi Tanıma: Oyun karakterlerinin isimlerini akıllıca çevirir  
- Renk Kodu Desteği: Oyunun renk kodlarını koruyarak çevirir  
- Manuel Kontrol: Klavye kısayolları ile duraklat/devam et  

🎮 Oyun Uyumluluğu  
- Otomatik bellek tarayıcı  
- Çoklu base address desteği  
- Cutscene ve dialog çevirisi  
- Hook temizleme ve geri yükleme  

## Gereksinimler

### Sistem Gereksinimleri  
- Python 3.8+  
- Windows 10/11 (64-bit)  
- Call of Duty: Infinite Warfare PC sürümü  
- Yönetici hakları (Administrator) - Bellek erişimi için zorunlu - Otomatik Yönetici olarak başlatmak için  start.bat dosyasını kullanabilirsiniz

### Python Kütüphaneleri  

Sözlük çeviri Kullanılacaksa:

```bash
pip install pymem pynput
````

Ai Model Kullanılacaksa:
```bash
pip install pymem torch transformers pynput
````

* pymem - Bellek okuma/yazma
* torch - PyTorch framework
* transformers - Hugging Face modelleri
* pynput - Klavye dinleyici

### GPU Desteği için (İsteğe bağlı)

* CUDA Toolkit 11.8+
* PyTorch CUDA sürümü

## Kurulum

Repository'yi klonlayın:

```bash
git clone https://github.com/yourusername/cod-iw-translator.git
cd cod-iw-translator
```

Gerekli kütüphaneleri yükleyin:

```bash
pip install -r requirements.txt
```

Oyunu başlatın:
Call of Duty: Infinite Warfare'i çalıştırın
Ana menüde Campaign menüsüne giriş yapın

## Kullanım

### İlk Çalıştırma

```bash
python cod-iw-localization.py
```

### Çeviri Modu Seçimi:

* Seçenek 1: AI Model + Cache (Mevcut Sözlük İle Çevrilmiş)

  * GPU üzerinde NLLB-200 modeli yükler
  * Yeni metinleri AI ile çevirir
  * Cache'deki çevirileri kullanır
* Seçenek 2: Sadece Cache (Hızlı)

  * GPU kullanmaz, model yüklemez
  * Sadece önceden çevrilmiş metinleri kullanır
  * Daha az kaynak tüketir

### Klavye Kontrolleri

* * (*): Çeviri sistemini duraklat
* * (-): Çeviri sistemini devam ettir
* Ctrl+C: Programdan çık

### Kullanım Senaryoları

**Yeni Çeviri (AI Model + Cache):**

```bash
python cod-iw-localization.py
# Seçim: 1 (AI Model + Cache)
# GPU seçimi yapın
# Model yüklenecek ve çeviri başlayacak
```

**Sözlük Çeviri (Cache Only):**

```bash
python cod-iw-localization.py
# Seçim: 2 (Sadece Cache)
# Model yüklenmez, anında başlar
```

## Dosya Yapısı

```
cod-iw-translator/
├── cod-iw-localization.py     # Ana program
├── translation_cache.json     # Çeviri önbelleği
├── dictionary.json            # Öntanımlı çeviriler
├── requirements.txt           # Python gereksinimleri
└── README.md                  # Bu dosya
```

## Performans İpuçları

### GPU Kullanımı

* NVIDIA GPU: CUDA desteği ile 5-10x hızlanma
* AMD GPU: CPU modu kullanılır
* Entegre GPU: CPU modu önerilir

### Bellek Optimizasyonu

* Cache Only Modu: \~50MB RAM kullanımı
* AI Model Modu: \~2-4GB GPU VRAM gerekir
* Batch İşleme: Çoklu çeviri optimizasyonu

### Sistem Ayarları

* Yönetici Hakları: Mutlaka gerekli
* Antivirus: Bellek erişimi için istisna ekleyin
* Windows Defender: Real-time protection geçici olarak kapatın

## Sorun Giderme

### Yaygın Hatalar

**"Process not found" Hatası:**

```plaintext
Çözüm: Oyunun çalıştığından emin olun
iw7_ship.exe process'i aktif olmalı
```

**"Access Denied" Hatası:**

```plaintext
Çözüm: Yönetici hakları ile çalıştırın
Sağ tık -> "Run as Administrator"
```

**GPU Bulunamadı:**

```plaintext
Çözüm: CPU modunu kullanın
PyTorch CUDA kurulumunu kontrol edin
```

**Model Yükleme Hatası:**

```plaintext
Çözüm: İnternet bağlantısını kontrol edin
Hugging Face model cache'ini temizleyin
```

### Debug Modu

Verbose çıktı için:

```bash
python cod-iw-localization.py --debug
```


## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için LICENSE dosyasına bakın.

## Teknik Detaylar

### Bellek Analizi

* Base Address Taraması: Oyun durumuna göre dinamik adres bulma
* String Table Analizi: Subtitle entry'lerini tanımlama
* Hook Sistemi: Pointer yönlendirme ve direct edit

### AI Modeli

* Model: facebook/nllb-200-distilled-1.3B
* Dil Çifti: İngilizce (eng\_Latn) → Türkçe (tur\_Latn)
* Batch İşleme: Optimized grup çevirisi

### Cache Sistemi

* EN→TR Cache: İngilizce'den Türkçe çeviri önbelleği
* TR→EN Reverse: Türkçe'den İngilizce ters lookup
* Character Names: Karakter ismi çevirileri


### Klavye Dinleme Sistemi

* Bölüm Geçişlerinde oyunun çökmesini engellemek için (*) ile çeviri sistemini duraklat
* Tekrar Devam Ettirmek için (-) ile çeviri sistemini devam ettir



⚠️ **Yasal Uyarı:** Bu araç yalnızca eğitim ve kişisel kullanım amaçlı geliştirilmiştir. Ticari bir amaç taşımamaktadır. Call of Duty: Infinite Warfare ve ilgili tüm telif hakları Activision ve Infinity Ward'a aittir. Bu araç, oyunun orijinal dosyalarını değiştirmez ve sadece bellek üzerinde geçici değişiklikler yapar.

---

### Önemli Not:

Kod bellek manipülasyonu yaptığından oyunda zaman zaman çökmeler yaşanabilir. Tam bir çeviri isteyenler **subtitle\_patterns** sınıfını şu şekilde güncellesin:

```python
subtitle_patterns = ["vidsubtitles", "subtitle_", "subtitles_", "menu", "attachments", "perks", "hud", "weapon"]
```

**Not:** Daha fazla bellek manipülasyonu daha fazla çökmelere sebep olabilir.

