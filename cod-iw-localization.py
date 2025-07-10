import pymem
import struct
import json
import sys
import time
import re
import os
import ctypes
from ctypes import wintypes
import threading
import pynput
from pynput import keyboard

class GameTranslator:
    def __init__(self):
        self.pm = pymem.Pymem("iw7_ship.exe")
        
        # Base addresses for different game states
        self.base_addresses = [
            0x35135B0,  # Ana base address
            0x3513000,  # Alternatif 1
            0x3514000,  # Alternatif 2
            0x3515000,  # Cutscene base
            0x3516000,  # Dialog base
        ]
        
        # Statistics tracking
        self.stats = {
            'scan_count': 0,
            'total': 0,
            'batch_count': 0,
            'hooks': 0,
            'direct_edit': 0,
            'errors': 0,
            'dictionary': 0,
            'cache': 0,
            'ai': 0,
            'skipped': 0,
            'cache_saved': 0,
            'speed': 0.0,
            'translated': 0,
            'gpu_active': False,
            'start_time': 0,
            'not_found': 0  # Cache'de bulunamayan metinler için
        }
        
        # Game state tracking - SADELEŞTİRİLDİ
        self.current_base = None
        self._ui_initialized = False
        self._ui_lock = threading.Lock()
        self._ui_thread_running = False
        
        # Manuel kontrol sistemi
        self.pause_mode = False
        self.keyboard_listener = None
        
        # Kontrol tuşları
        self.pause_key = '*'  # Duraklat
        self.resume_key = '-'  # Devam et
        
        # AI Model kullanım tercihi
        self.use_ai_model = self.ask_ai_model_preference()
        
        # Find active base
        self.find_active_base()
        
        # Translation caches and dictionary
        self.dictionary = {}  # Predefined translations
        self.translation_cache = {}  # EN->TR
        self.reverse_cache = {}  # TR->EN
        self.character_name_cache = {}  # Character names
        self.load_cache()
        self.load_dictionary()
        
        # NLLB-200 model - PERSISTANT LOADING (sadece AI model kullanılacaksa)
        self.model = None
        self.tokenizer = None
        self.device = None
        self.model_loaded = False
        
        # AI model kullanılacaksa torch ve transformers import et
        if self.use_ai_model:
            try:
                global torch, AutoTokenizer, AutoModelForSeq2SeqLM
                import torch
                from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
                self.device = self.select_gpu()
            except ImportError as e:
                print(f"\n❌ AI model için gerekli kütüphaneler bulunamadı: {e}")
                print("Lütfen aşağıdaki komutları çalıştırın:")
                print("pip install torch transformers")
                print("Şimdilik sadece cache modu kullanılacak.")
                self.use_ai_model = False
                input("\nDevam etmek için bir tuşa basın...")
        
        # Memory tracking - basitleştirildi
        self.hooked_entries = {}
        
        # Kernel32 for memory operations
        self.kernel32 = ctypes.windll.kernel32
        
        # Character name translations
        self.character_translations = {
            "Wolf": "Kurt",
            "Reyes": "Reyes",
            "Salter": "Salter", 
            "Ethan": "Ethan",
            "Omar": "Omar",
            "Kashima": "Kashima",
            "Brooks": "Brooks",
            "MacCallister": "MacCallister"
        }
        
        # Hook temizleme optimize edildi
        self.last_cleanup_time = time.time()
        self.cleanup_interval = 300  # 5 dakikada bir temizle (daha az sıklıkta)

    def ask_ai_model_preference(self):
        """Kullanıcıdan AI model kullanım tercihi sor"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n╔═══════════════════════════════════════════════════════════════╗")
        print("║               COD IW Smart Translator v3.2                   ║")
        print("╠═══════════════════════════════════════════════════════════════╣")
        print("║                    ÇEVİRİ MODU SEÇİMİ                        ║")
        print("╠═══════════════════════════════════════════════════════════════╣")
        print("║  1. AI Model + Cache Kullan (Önerilen)                       ║")
        print("║     - GPU üzerinde NLLB-200 modeli yükler                    ║")
        print("║     - Yeni metinleri AI ile çevirir                          ║")
        print("║     - Cache'deki çevirileri kullanır                         ║")
        print("║     - Gerekli: torch, transformers kütüphaneleri             ║")
        print("║                                                               ║")
        print("║  2. Sadece Cache Kullan (Hızlı)                              ║")
        print("║     - Sadece önceden çevrilmiş metinleri kullanır            ║")
        print("║     - GPU kullanmaz, daha az kaynak tüketir                  ║")
        print("║     - Yeni metinler çevrilmez                                ║")
        print("║     - Ek kütüphane gerektirmez                               ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        
        while True:
            try:
                choice = input("\nSeçiminizi yapın (1 veya 2): ").strip()
                if choice == "1":
                    print("\n✅ AI Model + Cache modu seçildi.")
                    print("Gerekli kütüphaneler kontrol edilecek...")
                    time.sleep(2)
                    return True
                elif choice == "2":
                    print("\n✅ Sadece Cache modu seçildi.")
                    print("Model yüklenmeyecek, sadece cache kullanılacak...")
                    time.sleep(2)
                    return False
                else:
                    print("❌ Lütfen 1 veya 2 seçin.")
            except KeyboardInterrupt:
                print("\n\nÇıkış yapılıyor...")
                sys.exit(0)
            except:
                print("❌ Geçersiz giriş. Lütfen 1 veya 2 seçin.")

    def start_keyboard_listener(self):
        """Klavye dinleyicisi başlat"""
        def on_press(key):
            try:
                if hasattr(key, 'char') and key.char:
                    if key.char == self.pause_key:
                        self.pause_translation_system()
                    elif key.char == self.resume_key:
                        self.resume_translation_system()
            except AttributeError:
                pass
        
        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()

    def pause_translation_system(self):
        """Çeviri sistemini duraklat"""
        if self.pause_mode:
            return
            
        self.pause_mode = True
        self.clean_all_hooks()
        self.stats['hooks'] = 0
        self.stats['direct_edit'] = 0

    def resume_translation_system(self):
        """Çeviri sistemini yeniden başlat"""
        if not self.pause_mode:
            return
            
        self.pause_mode = False
        self.find_active_base()
        self.hooked_entries.clear()

    def clean_all_hooks(self):
        """Tüm hookları güvenli şekilde temizle"""
        cleaned = 0
        
        for entry_id, hook_info in list(self.hooked_entries.items()):
            try:
                if hook_info.get('direct_edit', False):
                    self.restore_original_text(hook_info)
                else:
                    self.restore_original_pointer(hook_info)
                cleaned += 1
            except Exception:
                pass
        
        self.hooked_entries.clear()
        return cleaned

    def restore_original_pointer(self, hook_info):
        """Orijinal pointer'ı geri yükle"""
        try:
            PAGE_READWRITE = 0x04
            old_protect = wintypes.DWORD()
            
            self.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(hook_info['table_pos']),
                8,
                PAGE_READWRITE,
                ctypes.byref(old_protect)
            )
            
            self.pm.write_bytes(
                hook_info['table_pos'], 
                struct.pack("Q", hook_info['original_addr']), 
                8
            )
            
            self.kernel32.FlushInstructionCache(
                self.pm.process_handle,
                ctypes.c_void_p(hook_info['table_pos']),
                8
            )
            
            if hook_info['new_addr'] != hook_info['original_addr']:
                try:
                    self.pm.free(hook_info['new_addr'])
                except:
                    pass
        except Exception:
            pass

    def restore_original_text(self, hook_info):
        """Direct edit için orijinal metni geri yükle"""
        try:
            original_text = hook_info.get('original_text', '')
            if not original_text:
                return
                
            encoded_text = original_text.encode('utf-8') + b"\x00"
            size = len(encoded_text)
            
            PAGE_READWRITE = 0x04
            old_protect = wintypes.DWORD()
            
            self.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(hook_info['original_addr']),
                size,
                PAGE_READWRITE,
                ctypes.byref(old_protect)
            )
            
            self.pm.write_bytes(hook_info['original_addr'], encoded_text, size)
            
            self.kernel32.FlushInstructionCache(
                self.pm.process_handle,
                ctypes.c_void_p(hook_info['original_addr']),
                size
            )
        except Exception:
            pass

    def select_gpu(self):
        """GPU seçimi - sadece AI model kullanılacaksa"""
        if not self.use_ai_model:
            return None
            
        if not torch.cuda.is_available():
            return "cpu"
        
        gpu_count = torch.cuda.device_count()
        if gpu_count == 1:
            return "cuda:0"
        
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n╔═══════════════════════════════════════════════════════════════╗")
        print("║               COD IW Smart Translator v3.2                   ║")
        print("╠═══════════════════════════════════════════════════════════════╣")
        print("║  Birden fazla GPU tespit edildi. Kullanılacak GPU'yu seçin:  ║")
        print("╠═══════════════════════════════════════════════════════════════╣")
        
        for i in range(gpu_count):
            gpu_name = torch.cuda.get_device_name(i)
            props = torch.cuda.get_device_properties(i)
            gpu_memory = props.total_memory / (1024**3)
            print(f"║  {i}: {gpu_name[:40]:<40} {gpu_memory:.1f} GB  ║")
        
        print("╚═══════════════════════════════════════════════════════════════╝")
        
        while True:
            try:
                selection = int(input(f"\nGPU seçiniz (0-{gpu_count-1}): "))
                if 0 <= selection < gpu_count:
                    return f"cuda:{selection}"
                else:
                    print(f"Lütfen geçerli bir GPU indeksi girin (0-{gpu_count-1}).")
            except ValueError:
                print("Lütfen bir sayı girin.")

    def update_ui(self):
        """UI güncelleme - optimize edildi"""
        with self._ui_lock:
            if self._ui_initialized:
                lines_to_clear = 16 if self.pause_mode else 14
                if self.stats['gpu_active']:
                    lines_to_clear = 20 if self.pause_mode else 18
                sys.stdout.write(f"\033[{lines_to_clear}F\033[J")
            else:
                self._ui_initialized = True
            
            progress = self.stats['translated'] / max(self.stats['total'], 1) * 100
            bar_length = 40
            filled_length = int(bar_length * progress / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            remaining = self.stats['total'] - self.stats['translated']
            if self.stats['speed'] > 0:
                eta_seconds = remaining / self.stats['speed']
                eta_minutes = int(eta_seconds // 60)
                eta_seconds = int(eta_seconds % 60)
                eta = f"{eta_minutes}:{eta_seconds:02d}"
            else:
                eta = "--:--"
            
            status_color = "🛑" if self.pause_mode else "🟢"
            status_text = "DURAKLATILDI" if self.pause_mode else "AKTİF"
            
            # Çeviri modu göstergesi
            mode_text = "AI+Cache" if self.use_ai_model else "Cache Only"
            mode_color = "🤖" if self.use_ai_model else "💾"
            
            ui = (
                "╔═══════════════════════════════════════════════════════════════╗\n"
                f"║               COD IW Smart Translator v3.2                   ║\n"
                "╠═══════════════════════════════════════════════════════════════╣\n"
                f"║ {status_color} Durum: {status_text:<15} │ {mode_color} Mod: {mode_text:<12} ║\n"
                f"║ Tarama: {self.stats['scan_count']:<6} │ Bulunan: {self.stats['total']:<6} │ Hooklar: {len(self.hooked_entries):<6} ║\n"
                f"║ Hook: {self.stats['hooks']:<9} │ DirectEdit: {self.stats['direct_edit']:<5} │ Hata: {self.stats['errors']:<7} ║\n"
                f"║ Sözlük: {self.stats['dictionary']:<7} │ Cache: {self.stats['cache']:<9} │ AI: {self.stats['ai']:<9} ║\n"
                f"║ Atlanan: {self.stats['skipped']:<6} │ Bulunamadı: {self.stats['not_found']:<6} │ Hız: {self.stats['speed']:.1f}/s ║\n"
            )
            
            if self.stats['gpu_active']:
                ui += "╠═══════════════════════════════════════════════════════════════╣\n"
                ui += f"║ GPU Çeviri:   {self.stats['translated']}/{self.stats['total']}  ({progress:.1f}%)              ║\n"
                ui += f"║ [{bar}] ║\n"
                ui += f"║ Kalan süre: {eta}                                    ║\n"
            
            ui += "╠═══════════════════════════════════════════════════════════════╣\n"
            
            if self.pause_mode:
                ui += f"║ 🛑 SİSTEM DURAKLATILDI - Sahne değiştirin ve '-' basın       ║\n"
                ui += f"║ Kontroller: [*] Duraklat | [-] Devam | [Ctrl+C] Çıkış       ║\n"
            else:
                ui += f"║ 🔄 Çeviri işlemi devam ediyor...                              ║\n"
                ui += f"║ Kontroller: [*] Duraklat | [-] Devam | [Ctrl+C] Çıkış       ║\n"
            
            ui += "╚═══════════════════════════════════════════════════════════════╝"
            
            print(ui, end='', flush=True)

    def ui_update_thread(self):
        """UI güncelleme thread'i - daha az sıklıkta"""
        while self._ui_thread_running:
            try:
                self.update_ui()
                time.sleep(2)  # 2 saniyede bir güncelle (daha az CPU)
            except:
                pass

    def start_ui_updates(self):
        """UI güncelleme thread'ini başlat"""
        if not self._ui_thread_running:
            self._ui_thread_running = True
            ui_thread = threading.Thread(target=self.ui_update_thread, daemon=True)
            ui_thread.start()

    def stop_ui_updates(self):
        """UI güncelleme thread'ini durdur"""
        self._ui_thread_running = False

    def load_dictionary(self):
        """Sözlük yükle"""
        try:
            if os.path.exists("dictionary.json"):
                with open("dictionary.json", "r", encoding="utf8") as f:
                    self.dictionary = json.load(f)
        except Exception:
            self.dictionary = {}

    def load_cache(self):
        """Cache yükle"""
        try:
            if os.path.exists("translation_cache.json"):
                with open("translation_cache.json", "r", encoding="utf8") as f:
                    cache_data = json.load(f)
                    self.translation_cache = cache_data.get("en_to_tr", {})
                    self.reverse_cache = cache_data.get("tr_to_en", {})
                    self.character_name_cache = cache_data.get("character_names", {})
        except Exception:
            pass

    def save_cache(self):
        """Cache kaydet"""
        try:
            cache_data = {
                "en_to_tr": self.translation_cache,
                "tr_to_en": self.reverse_cache,
                "character_names": self.character_name_cache
            }
            with open("translation_cache.json", "w", encoding="utf8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=4)
            self.stats['cache_saved'] += 1
        except Exception:
            pass

    def find_active_base(self):
        """Aktif base address bul - optimize edildi"""
        for base_offset in self.base_addresses:
            try:
                base_start = self.pm.base_address + base_offset
                end, = struct.unpack("Q", self.pm.read_bytes(base_start, 8))
                start = base_start + 8
                count = (end - start) // 16
                
                if count > 0 and count < 100000:
                    # Hızlı doğrulama - sadece 3 entry kontrol et
                    test_entries = 0
                    current_start = start
                    
                    for i in range(min(3, count)):
                        try:
                            string_o, id_o = struct.unpack("QQ", self.pm.read_bytes(current_start, 16))
                            current_start += 16
                            
                            string_content = self.read_null_safe(string_o, 50)
                            id_content = self.read_null_safe(id_o, 50)
                            
                            if string_content and id_content:
                                test_entries += 1
                        except:
                            break
                    
                    if test_entries >= 2:  # Daha az kontrol
                        self.current_base = base_offset
                        self.base_start = base_start
                        self.start = start
                        self.count = count
                        return True
            except:
                continue
        
        return False

    def scan_memory_simple(self):
        """BASİT bellek taraması - tek thread"""
        entries = {}
        current_start = self.start
        
        for i in range(self.count):
            try:
                string_o, id_o = struct.unpack("QQ", self.pm.read_bytes(current_start, 16))
                current_start += 16
                
                # Sadece gerekli okumaları yap
                id_content = self.read_null_safe(id_o, 100)
                
                # Hızlı subtitle kontrolü
                if not ("vidsubtitles" in id_content or "subtitle_" in id_content or "subtitles_" in id_content):
                    continue
                
                string_content = self.read_null_safe(string_o)
                
                if string_content and id_content:
                    entries[id_content] = {
                        'content': string_content,
                        'string_addr': string_o,
                        'table_pos': self.start + i * 16
                    }
            except:
                continue
        
        return entries

    def parse_color_coded_text(self, text):
        """Renk kodlu metin parse et"""
        parts = []
        current_pos = 0
        
        color_pattern = r'\^(.)'
        matches = list(re.finditer(color_pattern, text))
        
        if not matches:
            return [{'type': 'text', 'content': text, 'color': None}]
        
        for i, match in enumerate(matches):
            color_start = match.start()
            color_char = match.group(1)
            
            if current_pos < color_start:
                prev_text = text[current_pos:color_start]
                if prev_text.strip():
                    parts.append({'type': 'text', 'content': prev_text, 'color': None})
            
            text_start = match.end()
            
            if i + 1 < len(matches):
                text_end = matches[i + 1].start()
            else:
                text_end = len(text)
            
            colored_text = text[text_start:text_end]
            
            if colored_text:
                parts.append({
                    'type': 'colored_text',
                    'content': colored_text,
                    'color': color_char,
                    'color_code': f'^{color_char}'
                })
            
            current_pos = text_end
        
        return parts

    def is_character_name(self, text):
        """Karakter ismi kontrolü"""
        text = text.strip().rstrip(':').rstrip()
        
        known_characters = list(self.character_translations.keys())
        
        if text in known_characters:
            return True
        
        character_patterns = [
            r'^[A-Z][a-z]+$',
            r'^[A-Z][a-z]*[A-Z][a-z]*$',
            r'^[A-Z]+$',
        ]
        
        for pattern in character_patterns:
            if re.match(pattern, text) and len(text) >= 3 and len(text) <= 15:
                common_words = ['THE', 'AND', 'FOR', 'YOU', 'ARE', 'NOT', 'CAN', 'GET']
                if text.upper() not in common_words:
                    return True
        
        return False

    def translate_character_name(self, name):
        """Karakter ismi çevir"""
        clean_name = name.strip().rstrip(':').rstrip()
        
        if clean_name in self.character_translations:
            translated = self.character_translations[clean_name]
            if name.rstrip().endswith(':'):
                translated += ':'
            return translated
        
        if clean_name in self.character_name_cache:
            translated = self.character_name_cache[clean_name]
            if name.rstrip().endswith(':'):
                translated += ':'
            return translated
        
        self.character_name_cache[clean_name] = clean_name
        return name

    def smart_translate_with_colors(self, text):
        """Renk kodları ile akıllı çeviri"""
        if not text.strip():
            return text
        
        parts = self.parse_color_coded_text(text)
        result_parts = []
        
        for i, part in enumerate(parts):
            if part['type'] == 'colored_text':
                content = part['content'].strip()
                
                if i == 0 or (i == 1 and parts[0]['type'] == 'text' and not parts[0]['content'].strip()):
                    if self.is_character_name(content):
                        translated_name = self.translate_character_name(content)
                        result_parts.append({
                            'type': 'colored_text',
                            'content': translated_name,
                            'color': part['color'],
                            'color_code': part['color_code']
                        })
                    else:
                        translated_content = self.translate_text_simple(content)
                        result_parts.append({
                            'type': 'colored_text',
                            'content': translated_content,
                            'color': part['color'],
                            'color_code': part['color_code']
                        })
                else:
                    translated_content = self.translate_text_simple(content)
                    result_parts.append({
                        'type': 'colored_text',
                        'content': translated_content,
                        'color': part['color'],
                        'color_code': part['color_code']
                    })
            else:
                if part['content'].strip():
                    translated_content = self.translate_text_simple(part['content'])
                    result_parts.append({
                        'type': 'text',
                        'content': translated_content,
                        'color': None
                    })
                else:
                    result_parts.append(part)
        
        final_text = ""
        for part in result_parts:
            if part['type'] == 'colored_text':
                final_text += part['color_code'] + part['content']
            else:
                final_text += part['content']
        
        return final_text

    def load_nllb_model_once(self):
        """Model sadece bir kez yükle - PERSISTENT (sadece AI model kullanılacaksa)"""
        if not self.use_ai_model:
            return True  # AI model kullanılmayacaksa başarılı say
            
        if self.model_loaded:
            return True
            
        try:
            model_name = "facebook/nllb-200-distilled-1.3B"
            print(f"\nModel yükleniyor... (Bu işlem bir kez yapılıyor)")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name, 
                src_lang="eng_Latn", 
                tgt_lang="tur_Latn"
            )
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            
            print(f"Model {self.device} cihazına yükleniyor...")
            self.model.to(self.device)
            
            self.model_loaded = True
            print("Model başarıyla yüklendi ve bellekte tutulacak.")
            return True
            
        except Exception as e:
            print(f"Model yükleme hatası: {e}")
            return False

    def translate_text_simple(self, text):
        """Basit metin çevirisi - Cache only veya AI+Cache modu"""
        if not text.strip():
            return text
        
        clean_text = text.strip()
        
        # 1. Sözlük kontrolü
        if clean_text in self.dictionary:
            self.stats['dictionary'] += 1
            return self.dictionary[clean_text]
        
        # 2. Cache kontrolü
        if clean_text in self.translation_cache:
            self.stats['cache'] += 1
            return self.translation_cache[clean_text]
        
        # 3. Reverse cache kontrolü
        if clean_text in self.reverse_cache:
            return text
        
        # 4. AI model kullanılmayacaksa burada dur
        if not self.use_ai_model:
            self.stats['not_found'] += 1
            return text  # Orijinal metni geri döndür
        
        # 5. GPU çevirisi (sadece AI model kullanılacaksa)
        if not self.model_loaded:
            self.stats['not_found'] += 1
            return text
        
        try:
            self.stats['ai'] += 1
            
            self.tokenizer.src_lang = "eng_Latn"
            inputs = self.tokenizer(
                clean_text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=512
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            try:
                if hasattr(self.tokenizer, 'get_lang_id'):
                    forced_bos_token_id = self.tokenizer.get_lang_id("tur_Latn")
                elif hasattr(self.tokenizer, 'lang_code_to_id'):
                    forced_bos_token_id = self.tokenizer.lang_code_to_id["tur_Latn"]
                else:
                    forced_bos_token_id = self.tokenizer.convert_tokens_to_ids("tur_Latn")
            except:
                forced_bos_token_id = 256167
            
            translated_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_length=512,
                num_beams=4,
                early_stopping=True,
                do_sample=False
            )
            
            translated_text = self.tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        
            # Cache'e ekle
            self.translation_cache[clean_text] = translated_text
            self.reverse_cache[translated_text] = clean_text
            
            # Her 50 çeviride bir kaydet (daha az sıklıkta)
            if self.stats['ai'] % 50 == 0:
                self.save_cache()
            
            return translated_text
            
        except Exception:
            self.stats['errors'] += 1
            self.stats['not_found'] += 1
            return text

    def fallback_translate(self, text):
        """Fallback çeviri - sadece AI model kullanılacaksa"""
        if not self.use_ai_model:
            self.stats['not_found'] += 1
            return text
            
        try:
            simple_translations = {
                "Go! Go!": "Git! Git!",
                "Move out!": "Hareket et!",
                "Contact!": "Temas!",
                "Enemy down!": "Düşman devrildi!",
                "Reloading!": "Şarjör değiştiriyorum!"
            }
            
            clean_text = re.sub(r'\^.', '', text.strip())
            if clean_text in simple_translations:
                return simple_translations[clean_text]
            
            self.stats['not_found'] += 1
            return text
        except Exception:
            self.stats['not_found'] += 1
            return text

    def batch_translate_optimized(self, texts, batch_size=16):
        """Optimize edilmiş batch çeviri"""
        results = {}
        
        cache_hits = 0
        needs_translation = {}
        
        for entry_id, text in texts.items():
            clean_text = text.strip()
            
            if clean_text in self.dictionary:
                results[entry_id] = self.dictionary[clean_text]
                self.stats['dictionary'] += 1
                cache_hits += 1
            elif clean_text in self.translation_cache:
                results[entry_id] = self.translation_cache[clean_text]
                self.stats['cache'] += 1
                cache_hits += 1
            elif clean_text in self.reverse_cache:
                results[entry_id] = text
                cache_hits += 1
            else:
                needs_translation[entry_id] = text
        
        self.stats['total'] = len(texts)
        self.stats['translated'] = cache_hits
        
        if needs_translation:
            # AI model kullanılacaksa GPU aktif et
            if self.use_ai_model:
                self.stats['gpu_active'] = True
            
            self.stats['start_time'] = time.time()
            self.stats['batch_count'] = 1
            
            for entry_id, text in needs_translation.items():
                if "^" in text:
                    translated = self.smart_translate_with_colors(text)
                else:
                    translated = self.translate_text_simple(text)
                
                results[entry_id] = translated
                self.stats['translated'] += 1
                
                elapsed = time.time() - self.stats['start_time']
                self.stats['speed'] = self.stats['translated'] / elapsed if elapsed > 0 else 0
        
        self.stats['gpu_active'] = False
        return results

    def read_null_safe(self, addr, max_length=2048):
        """Güvenli string okuma"""
        try:
            ret = b""
            read_count = 0
            while read_count < max_length:
                byte = self.pm.read_bytes(addr + read_count, 1)
                if byte == b"\x00":
                    break
                ret += byte
                read_count += 1
            return ret.decode('utf-8', errors="ignore")
        except:
            return ""

    def allocate_string_memory_simple(self, text):
        """Basit bellek ayırma"""
        try:
            encoded_text = text.encode('utf-8') + b"\x00"
            size = len(encoded_text)
            
            new_addr = self.pm.allocate(size + 64)
            if new_addr == 0:
                return None
            
            self.pm.write_bytes(new_addr, encoded_text, len(encoded_text))
            
            verification = self.read_null_safe(new_addr)
            if verification == text:
                return new_addr
            else:
                return None
                
        except Exception:
            return None

    def direct_edit_translation(self, entry_id, original_addr, new_text):
        """Direct edit"""
        try:
            original_text = self.read_null_safe(original_addr)
            
            encoded_text = new_text.encode('utf-8') + b"\x00"
            size = len(encoded_text)
            
            PAGE_READWRITE = 0x04
            old_protect = wintypes.DWORD()
            
            result = self.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(original_addr),
                size,
                PAGE_READWRITE,
                ctypes.byref(old_protect)
            )
            
            self.pm.write_bytes(original_addr, encoded_text, size)
            
            self.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(original_addr),
                size,
                old_protect.value,
                ctypes.byref(old_protect)
            )
            
            self.kernel32.FlushInstructionCache(
                self.pm.process_handle,
                ctypes.c_void_p(original_addr),
                size
            )
            
            verification = self.read_null_safe(original_addr)
            if verification == new_text:
                self.hooked_entries[entry_id] = {
                    'original_addr': original_addr,
                    'new_addr': original_addr,
                    'table_pos': 0,
                    'original_text': original_text,
                    'new_text': new_text,
                    'hook_time': time.time(),
                    'direct_edit': True
                }
                self.stats['direct_edit'] += 1
                return True
            
            self.stats['errors'] += 1
            return False
            
        except Exception:
            self.stats['errors'] += 1
            return False

    def hook_translation_simple(self, entry_id, table_pos, original_addr, new_text):
        """Basit hook işlemi"""
        try:
            if self.pause_mode:
                return False
                
            original_text = self.read_null_safe(original_addr)
            
            if entry_id.startswith("vidsubtitles"):
                success = self.direct_edit_translation(entry_id, original_addr, new_text)
                if success:
                    if entry_id in self.hooked_entries:
                        self.hooked_entries[entry_id]['original_text'] = original_text
                return success
            
            new_addr = self.allocate_string_memory_simple(new_text)
            if new_addr is None:
                self.stats['errors'] += 1
                return False
            
            try:
                PAGE_READWRITE = 0x04
                old_protect = wintypes.DWORD()
                self.kernel32.VirtualProtectEx(
                    self.pm.process_handle,
                    ctypes.c_void_p(table_pos),
                    8,
                    PAGE_READWRITE,
                    ctypes.byref(old_protect)
                )
            except:
                pass
            
            self.pm.write_bytes(table_pos, struct.pack("Q", new_addr), 8)
            
            try:
                self.kernel32.FlushInstructionCache(
                    self.pm.process_handle,
                    ctypes.c_void_p(table_pos),
                    8
                )
            except:
                pass
            
            try:
                time.sleep(0.01)
                new_pointer = struct.unpack("Q", self.pm.read_bytes(table_pos, 8))[0]
                hooked_text = self.read_null_safe(new_pointer)
                
                if new_pointer == new_addr and hooked_text == new_text:
                    self.hooked_entries[entry_id] = {
                        'original_addr': original_addr,
                        'new_addr': new_addr,
                        'table_pos': table_pos,
                        'original_text': original_text,
                        'new_text': new_text,
                        'hook_time': time.time()
                    }
                    self.stats['hooks'] += 1
                    return True
            except:
                pass
            
            self.stats['errors'] += 1
            return False
            
        except Exception:
            self.stats['errors'] += 1
            return False

    def clean_unused_hooks_minimal(self, current_entries):
        """MİNİMUM hook temizleme - çok daha az sıklıkta"""
        current_time = time.time()
        
        # 5 dakikada bir temizle
        if current_time - self.last_cleanup_time < self.cleanup_interval:
            return 0
        
        current_entry_ids = set(current_entries.keys())
        hooks_to_remove = []
        
        for entry_id in list(self.hooked_entries.keys()):
            if entry_id not in current_entry_ids:
                hooks_to_remove.append(entry_id)
        
        # En fazla 10 hook temizle (performans için)
        cleaned = 0
        for entry_id in hooks_to_remove[:10]:
            try:
                del self.hooked_entries[entry_id]
                cleaned += 1
            except:
                pass
        
        self.last_cleanup_time = current_time
        return cleaned

    def auto_translate_mode_enhanced(self):
        """Ana çeviri modu - PERFORMANS OPTİMİZE EDİLDİ"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Stats reset
        self.stats = {
            'scan_count': 0,
            'total': 0,
            'batch_count': 0,
            'hooks': 0,
            'direct_edit': 0,
            'errors': 0,
            'dictionary': 0,
            'cache': 0,
            'ai': 0,
            'skipped': 0,
            'cache_saved': 0,
            'speed': 0.0,
            'translated': 0,
            'gpu_active': False,
            'start_time': time.time(),
            'not_found': 0
        }
        
        # Klavye dinleyici
        self.start_keyboard_listener()
        
        # UI thread
        self.start_ui_updates()
        
        # Model sadece AI kullanılacaksa yükle
        if self.use_ai_model:
            if not self.load_nllb_model_once():
                self.stats['errors'] += 1
        else:
            print("\n💾 Cache-only modu aktif. Sadece önceden çevrilmiş metinler kullanılacak.")
            time.sleep(2)

        try:
            while True:
                # Pause kontrolü
                if self.pause_mode:
                    time.sleep(2)  # Pause modunda daha az kontrol
                    continue
                    
                self.stats['scan_count'] += 1
                
                # Base address kontrolü
                if not self.current_base:
                    if not self.find_active_base():
                        time.sleep(10)  # Bulamazsa daha uzun bekle
                        continue
                
                # SADECE BASİT TARAMA - threading kaldırıldı
                entries = self.scan_memory_simple()
                self.stats['total'] = len(entries)
                
                # Çevirilecek entry'leri topla
                to_translate = {}
                for entry_id, entry_data in entries.items():
                    if entry_id in self.hooked_entries:
                        continue
                    
                    to_translate[entry_id] = entry_data['content']
                
                # Batch çeviri
                if to_translate:
                    self.stats['start_time'] = time.time()
                    self.stats['translated'] = 0
                    
                    translations = self.batch_translate_optimized(to_translate)
                    
                    # Çevirileri uygula
                    for entry_id, translated_text in translations.items():
                        if self.pause_mode:
                            break
                            
                        original_text = to_translate[entry_id]
                        
                        if translated_text == original_text:
                            self.stats['skipped'] += 1
                            continue
                        
                        self.hook_translation_simple(
                            entry_id,
                            entries[entry_id]['table_pos'],
                            entries[entry_id]['string_addr'],
                            translated_text
                        )
                
                # Minimal hook temizleme
                self.clean_unused_hooks_minimal(entries)
                
                # Cache kaydet
                if self.stats['ai'] > 0 or self.stats['dictionary'] > 0:
                    self.save_cache()
                
                # UZUN BEKLEME - 15 saniye (CPU tüketimini azaltır)
                time.sleep(15)
                
        except KeyboardInterrupt:
            self.stop_ui_updates()
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            
            self.clean_all_hooks()
            self.save_cache()

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    
    try:
        translator = GameTranslator()
        translator.auto_translate_mode_enhanced()
    except Exception as e:
        print(f"\nUygulama hatası: {e}")
        input("\nDevam etmek için bir tuşa basın...")

if __name__ == "__main__":
    main()
