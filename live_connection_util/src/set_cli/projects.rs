use anyhow::{Context, Result, bail, ensure};
use serde::Deserialize;
use std::{
    collections::{HashMap, HashSet},
    fs,
    path::{Path, PathBuf},
};

#[derive(Deserialize)]
struct Setlist {
    projects: Vec<String>,
}

fn scan(folder: &Path, matches: &mut HashMap<String, Vec<PathBuf>>) -> Result<()> {
    for entry in fs::read_dir(folder).with_context(|| format!("Read {}", folder.display()))? {
        let entry = entry?;
        let path = entry.path();
        let kind = entry.file_type()?;
        if kind.is_dir() {
            scan(&path, matches)?;
        } else if path.extension().is_some_and(|ext| ext == "bwproject")
            && path.is_file()
            && let Some(name) = path.file_stem().and_then(|s| s.to_str())
            && let Some(paths) = matches.get_mut(name)
        {
            paths.push(path);
        }
    }
    Ok(())
}

pub fn resolve(setlist: &Path, root: &Path) -> Result<Vec<PathBuf>> {
    let set: Setlist = serde_json::from_slice(
        &fs::read(setlist).with_context(|| format!("Read {}", setlist.display()))?,
    )?;
    ensure!(
        !set.projects.is_empty() && set.projects.iter().all(|name| !name.trim().is_empty()),
        "Setlist must contain a nonempty projects list with no blank names"
    );
    ensure!(
        set.projects.iter().collect::<HashSet<_>>().len() == set.projects.len(),
        "Duplicate projects in setlist"
    );
    let root = root
        .canonicalize()
        .with_context(|| format!("Projects folder: {}", root.display()))?;
    ensure!(
        root.is_dir(),
        "Projects root is not a directory: {}",
        root.display()
    );
    let mut matches: HashMap<_, _> = set
        .projects
        .iter()
        .map(|name| (name.clone(), Vec::new()))
        .collect();
    scan(&root, &mut matches)?;
    set.projects
        .iter()
        .map(|name| {
            let paths = &matches[name];
            match paths.as_slice() {
                [path] => Ok(path.clone()),
                [] => bail!("No {name}.bwproject found under {}", root.display()),
                _ => bail!(
                    "Multiple matches for {name}; narrow --projects-root:\n{}",
                    paths
                        .iter()
                        .map(|p| p.display().to_string())
                        .collect::<Vec<_>>()
                        .join("\n")
                ),
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn preserves_order_and_rejects_ambiguous_or_missing_projects() {
        let dir = std::env::temp_dir().join(format!("vs-set-projects-{}", std::process::id()));
        fs::create_dir_all(dir.join("nested")).unwrap();
        let list = dir.join("set.json");
        fs::write(&list, r#"{"projects":["second","first"]}"#).unwrap();
        fs::write(dir.join("first.bwproject"), "").unwrap();
        assert!(resolve(&list, &dir).is_err());
        fs::write(dir.join("nested/second.bwproject"), "").unwrap();
        let paths = resolve(&list, &dir).unwrap();
        assert_eq!(paths[0].file_stem().unwrap(), "second");
        assert_eq!(paths[1].file_stem().unwrap(), "first");
        fs::write(dir.join("nested/first.bwproject"), "").unwrap();
        assert!(resolve(&list, &dir).is_err());
        fs::write(&list, r#"{"projects":["first","first"]}"#).unwrap();
        assert!(resolve(&list, &dir).is_err());
        fs::remove_dir_all(&dir).unwrap();
    }
}
