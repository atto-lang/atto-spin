use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::time::Duration;

pub struct Connection(BufReader<TcpStream>);
pub struct Response {
    pub worker: String,
    pub reused: bool,
}

fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}
impl Connection {
    pub fn connect(port: u16) -> io::Result<Self> {
        let stream = TcpStream::connect(("127.0.0.1", port))?;
        stream.set_nodelay(true)?;
        stream.set_read_timeout(Some(Duration::from_secs(5)))?;
        stream.set_write_timeout(Some(Duration::from_secs(5)))?;
        Ok(Self(BufReader::new(stream)))
    }
    pub fn request(&mut self, port: u16, mode: &str, sampled: bool) -> io::Result<Response> {
        write!(self.0.get_mut(), "GET /{mode} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Profile: {}\r\nConnection: keep-alive\r\n\r\n", if sampled { "yes" } else { "no" })?;
        let mut line = String::new();
        self.0.read_line(&mut line)?;
        if !line.starts_with("HTTP/1.1 200 ") {
            return Err(invalid("non-200 response"));
        }
        let mut length = None;
        let mut chunked = false;
        let mut actor_mode = String::new();
        let mut worker = String::new();
        let mut reused = false;
        let mut header_bytes = line.len();
        loop {
            line.clear();
            if self.0.read_line(&mut line)? == 0 {
                return Err(invalid("EOF in headers"));
            }
            header_bytes += line.len();
            if header_bytes > 16384 {
                return Err(invalid("oversized headers"));
            }
            if line == "\r\n" {
                break;
            }
            let (key, value) = line
                .split_once(':')
                .ok_or_else(|| invalid("invalid header"))?;
            let value = value.trim();
            match key.to_ascii_lowercase().as_str() {
                "content-length" => {
                    length = Some(
                        value
                            .parse::<usize>()
                            .map_err(|_| invalid("invalid length"))?,
                    )
                }
                "transfer-encoding" => chunked = value.eq_ignore_ascii_case("chunked"),
                "x-actor-mode" => actor_mode = value.into(),
                "x-worker" => worker = value.into(),
                "x-reused" => reused = value == "yes",
                _ => {}
            }
        }
        let mut body = Vec::new();
        if chunked {
            loop {
                line.clear();
                self.0.read_line(&mut line)?;
                let size = usize::from_str_radix(line.trim().split(';').next().unwrap_or(""), 16)
                    .map_err(|_| invalid("invalid chunk"))?;
                if size == 0 {
                    line.clear();
                    self.0.read_line(&mut line)?;
                    if line != "\r\n" {
                        return Err(invalid("unexpected trailers"));
                    }
                    break;
                }
                if body.len() + size > 1024 {
                    return Err(invalid("oversized body"));
                }
                let start = body.len();
                body.resize(start + size, 0);
                self.0.read_exact(&mut body[start..])?;
                let mut crlf = [0; 2];
                self.0.read_exact(&mut crlf)?;
                if crlf != *b"\r\n" {
                    return Err(invalid("invalid chunk terminator"));
                }
            }
        } else {
            let length = length.ok_or_else(|| invalid("missing response framing"))?;
            if length > 1024 {
                return Err(invalid("oversized body"));
            }
            body.resize(length, 0);
            self.0.read_exact(&mut body)?;
        }
        if body != b"ok\n" || actor_mode != mode || worker.is_empty() {
            return Err(invalid("body or actor identity mismatch"));
        }
        Ok(Response { worker, reused })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;
    fn serve(bytes: &'static [u8]) -> (u16, std::thread::JoinHandle<()>) {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let thread = std::thread::spawn(move || {
            let (stream, _) = listener.accept().unwrap();
            let mut input = BufReader::new(stream);
            let mut line = String::new();
            loop {
                line.clear();
                input.read_line(&mut line).unwrap();
                if line == "\r\n" {
                    break;
                }
            }
            input.get_mut().write_all(bytes).unwrap();
        });
        (port, thread)
    }
    #[test]
    fn reads_chunked_and_content_length_responses() {
        for bytes in [
            &b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nX-Actor-Mode: shared\r\nX-Worker: worker-7\r\nX-Reused: yes\r\n\r\nok\n"[..],
            &b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nX-Actor-Mode: shared\r\nX-Worker: worker-7\r\nX-Reused: yes\r\n\r\n3\r\nok\n\r\n0\r\n\r\n"[..]
        ] {
            let (port, server) = serve(bytes);
            let response = Connection::connect(port).unwrap().request(port, "shared", false).unwrap();
            assert_eq!(response.worker, "worker-7"); assert!(response.reused);
            server.join().unwrap();
        }
    }
    #[test]
    fn rejects_wrong_mode_and_bad_framing() {
        for bytes in [
            &b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nX-Actor-Mode: isolated\r\nX-Worker: worker-7\r\n\r\nok\n"[..],
            &b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\ngarbage\r\n"[..]
        ] {
            let (port, server) = serve(bytes);
            assert!(Connection::connect(port).unwrap().request(port, "shared", false).is_err());
            server.join().unwrap();
        }
    }
}
