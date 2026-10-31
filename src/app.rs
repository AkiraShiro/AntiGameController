use crate::{autostart, config::{self, Config}, hosts, processes, profiles, updater};
use eframe::egui;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub fn run() -> eframe::Result<()> {
    let options = eframe::NativeOptions { viewport: egui::ViewportBuilder::default().with_inner_size([900.0, 650.0]), ..Default::default() };
    eframe::run_native("AntiGame Controller", options, Box::new(|_| Ok(Box::new(App::new()))))
}

struct App {
    config: Arc<Mutex<Config>>,
    status: String,
    protection: bool,
    last_tick: Instant,
    process_input: String,
    website_input: String,
    password_input: String,
    password_error: String,
    import_input: String,
    selected_profile: String,
    old_password: String,
    new_password: String,
}

impl App {
    fn new() -> Self {
        let config = Arc::new(Mutex::new(config::load()));
        crate::network::start(config.clone());
        Self { config, status: "Готово".into(), protection: false, last_tick: Instant::now(), process_input: String::new(), website_input: String::new(), password_input: String::new(), password_error: String::new(), import_input: String::new(), selected_profile: String::new(), old_password: String::new(), new_password: String::new() }
    }
    fn save(&mut self) { if let Ok(cfg) = self.config.lock() { self.status = config::save(&cfg).map(|_| "Конфигурация сохранена".into()).unwrap_or_else(|e| e.to_string()); } }
    fn run_protection(&mut self) {
        let cfg = self.config.lock().unwrap().clone();
        let killed = processes::kill_matching(&cfg.blocked_processes);
        self.status = format!("Завершено процессов: {}", killed.len());
        if let Err(e) = hosts::block(&cfg.blocked_websites) { self.status = format!("Ошибка hosts: {e}"); }
    }
    fn authorized(&mut self) -> bool {
        let password = self.password_input.clone();
        let expected = self.config.lock().unwrap().password_hash.clone();
        if config::sha256(&password) == expected { self.password_input.clear(); self.password_error.clear(); true }
        else { self.password_error = "Неверный пароль".into(); false }
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        if self.protection && self.last_tick.elapsed() >= Duration::from_secs(self.config.lock().unwrap().check_interval.max(1)) { self.run_protection(); self.last_tick = Instant::now(); }
        egui::TopBottomPanel::top("header").show(ctx, |ui| { ui.horizontal(|ui| { ui.heading("AntiGame Controller"); ui.separator(); ui.label(&self.status); }); });
        egui::CentralPanel::default().show(ctx, |ui| {
            let mut cfg = self.config.lock().unwrap();
            ui.columns(2, |columns| {
                columns[0].heading("Процессы");
                columns[0].horizontal(|ui| { ui.text_edit_singleline(&mut self.process_input); if ui.button("Добавить").clicked() && !self.process_input.trim().is_empty() { cfg.blocked_processes.push(self.process_input.trim().into()); self.process_input.clear(); } });
                let mut remove_process = None;
                for (i, item) in cfg.blocked_processes.iter().enumerate() { columns[0].horizontal(|ui| { ui.label(item); if ui.small_button("Удалить").clicked() { remove_process = Some(i); } }); }
                if let Some(i) = remove_process { cfg.blocked_processes.remove(i); }
                columns[1].heading("Сайты");
                columns[1].horizontal(|ui| { ui.text_edit_singleline(&mut self.website_input); if ui.button("Добавить").clicked() && !self.website_input.trim().is_empty() { cfg.blocked_websites.push(self.website_input.trim().into()); self.website_input.clear(); } });
                let mut remove_site = None;
                for (i, item) in cfg.blocked_websites.iter().enumerate() { columns[1].horizontal(|ui| { ui.label(item); if ui.small_button("Удалить").clicked() { remove_site = Some(i); } }); }
                if let Some(i) = remove_site { cfg.blocked_websites.remove(i); }
            });
            ui.separator();
            ui.horizontal(|ui| { ui.checkbox(&mut self.protection, "Защита активна"); ui.checkbox(&mut cfg.enable_process_protection, "Защищать процессы"); ui.checkbox(&mut cfg.enable_autostart, "Автозапуск"); ui.checkbox(&mut cfg.host_mode, "Режим HOST"); ui.checkbox(&mut cfg.auto_update, "Автообновление"); ui.add(egui::DragValue::new(&mut cfg.check_interval).prefix("Интервал: ")); });
            ui.horizontal(|ui| {
                if ui.button("Применить блокировки").clicked() { drop(cfg); if self.authorized() { self.run_protection(); } }
                if ui.button("Остановить и разблокировать").clicked() { drop(cfg); if self.authorized() { self.protection = false; self.status = hosts::unblock().map(|_| "Блокировки сняты".into()).unwrap_or_else(|e| e.to_string()); } }
                if ui.button("Сохранить").clicked() { drop(cfg); self.save(); }
                if ui.button("Проверить обновления").clicked() { drop(cfg); let mut owned = self.config.lock().unwrap(); self.status = match updater::check_and_stage(&mut owned) { Ok(Some(v)) => format!("Доступна версия {v}, перезапустите приложение"), Ok(None) => "Установлена последняя версия".into(), Err(e) => e }; }
            });
            ui.horizontal(|ui| { if ui.button("Сохранить профиль").clicked() { let _ = profiles::save(&cfg.profile_name, &cfg); self.status = "Профиль сохранен".into(); } if ui.button("Настроить автозапуск").clicked() { self.status = if autostart::ensure(cfg.enable_autostart) { "Автозапуск обновлен".into() } else { "Не удалось обновить автозапуск".into() }; } });
            ui.separator();
            ui.collapsing("Пароль и профили", |ui| {
                ui.horizontal(|ui| { ui.label("Пароль:"); ui.add(egui::TextEdit::singleline(&mut self.password_input).password(true)); });
                if !self.password_error.is_empty() { ui.colored_label(egui::Color32::RED, &self.password_error); }
                ui.horizontal(|ui| { ui.label("Текущий:"); ui.add(egui::TextEdit::singleline(&mut self.old_password).password(true)); ui.label("Новый:"); ui.add(egui::TextEdit::singleline(&mut self.new_password).password(true)); if ui.button("Сменить").clicked() { let expected = cfg.password_hash.clone(); if config::sha256(&self.old_password) == expected && !self.new_password.is_empty() { cfg.password_hash = config::sha256(&self.new_password); self.old_password.clear(); self.new_password.clear(); self.status = "Пароль изменен".into(); } else { self.password_error = "Текущий пароль неверен".into(); } } });
                if ui.button("Экспорт JSON").clicked() { self.status = profiles::export_json(&cfg).unwrap_or_else(|e| e.to_string()); }
                ui.label("Импорт JSON");
                ui.add(egui::TextEdit::multiline(&mut self.import_input).desired_rows(3));
                if ui.button("Импортировать профиль").clicked() {
                    drop(cfg);
                    if self.authorized() {
                        let payload = self.import_input.clone();
                        match profiles::import_json(&payload) {
                            Ok(imported) => {
                                *self.config.lock().unwrap() = imported;
                                self.import_input.clear();
                                self.status = "Профиль импортирован".into();
                            }
                            Err(error) => self.status = error,
                        }
                    }
                }
                ui.horizontal(|ui| {
                    egui::ComboBox::from_id_salt("profile_selector").selected_text(if self.selected_profile.is_empty() { "Выберите профиль" } else { &self.selected_profile }).show_ui(ui, |ui| {
                        for profile in profiles::list() { ui.selectable_value(&mut self.selected_profile, profile.id, format!("{} ({})", profile.name, profile.created)); }
                    });
                    let load_clicked = ui.button("Загрузить").clicked();
                    let delete_clicked = ui.button("Удалить").clicked();
                    if load_clicked {
                        drop(cfg);
                        if self.authorized() {
                            if let Some(loaded) = profiles::load(&self.selected_profile) { *self.config.lock().unwrap() = loaded; self.status = "Профиль загружен".into(); }
                        }
                    } else if delete_clicked {
                        drop(cfg);
                        if self.authorized() && profiles::delete(&self.selected_profile).is_ok() { self.selected_profile.clear(); self.status = "Профиль удален".into(); }
                    }
                });
            });
        });
        ctx.request_repaint_after(Duration::from_millis(250));
    }
}