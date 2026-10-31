#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod app;
mod autostart;
mod config;
mod hosts;
mod network;
mod processes;
mod profiles;
mod updater;

fn main() -> eframe::Result<()> {
    app::run()
}