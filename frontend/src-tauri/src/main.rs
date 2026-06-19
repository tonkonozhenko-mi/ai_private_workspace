// Build the release binary as a Windows GUI app (subsystem "windows") so it does
// not open a console window. Without this, the packaged Windows app launches with
// a terminal attached, and closing that terminal kills the app. Debug builds keep
// the console so developer logs stay visible.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    ai_private_workspace_lib::run();
}
