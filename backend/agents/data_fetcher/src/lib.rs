//! Atheon AI Data Fetcher Agent Library
//!
//! This library provides the core functionality for the data fetcher agent,
//! which is responsible for making HTTP requests to external APIs and services.

pub mod models;
pub mod fetcher;
pub mod kafka;
pub mod errors;

// Re-export commonly used types
pub use models::{FetchRequest, FetchResult, Config};
pub use fetcher::HttpFetcher;
pub use errors::FetchError;