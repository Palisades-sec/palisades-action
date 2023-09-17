import argparse
import base64
import json
import os
from copy import deepcopy
from uuid import uuid4

import requests
from langchain.document_loaders import DirectoryLoader
from langchain.embeddings import HuggingFaceInferenceAPIEmbeddings
from langchain.schema import Document
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS

from schemas import GitHubIssue

# from feature_agent import feature_development_agent, agent_prompt

# embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
embeddings = HuggingFaceInferenceAPIEmbeddings(
    api_key=os.environ["HF_TOKEN"], model_name="sentence-transformers/all-MiniLM-l6-v2"
)
token = os.environ["GITHUB_TOKEN"]
headers = {"Authorization": f"token {token}"}


def get_source_chunks(files):
    source_chunks = []
    splitter = CharacterTextSplitter(separator=" ", chunk_size=1024, chunk_overlap=0)
    for source in files:
        for chunk in splitter.split_text(source.page_content):
            source_chunks.append(
                Document(page_content=chunk, metadata=deepcopy(source.metadata))
            )
    return source_chunks


def create_vector_db(repository_name):
    repo_name = repository_name.split("/")[1]
    loader = DirectoryLoader(f"./tmp/", glob="**/*.py")
    data = loader.load()
    FAISS_DB_PATH = f"./FAISS/{os.path.basename(repository_name)}"
    faiss_db = None
    if not os.path.exists(FAISS_DB_PATH):
        source_chunks = get_source_chunks(data)
        faiss_db = FAISS.from_documents(source_chunks, embeddings)
        faiss_db.save_local(FAISS_DB_PATH)
    else:
        faiss_db = FAISS.load_local(FAISS_DB_PATH, embeddings)
    return faiss_db


def send_data(issue, vector_db: FAISS, cf_auth_token):
    issue_data = f"Title: {issue.title}\n\n{issue.body}"
    retrieved_docs = vector_db.similarity_search(issue_data, k=4)
    complete_file = vector_db.similarity_search(
        issue_data, filter=retrieved_docs[0].metadata
    )
    retrieved_content = [
        f"From path {docs.metadata['source']}\n{docs.page_content}"
        for docs in retrieved_docs
    ]
    retrieved_content = "\n".join(retrieved_content)
    body = {"issue": issue_data, "retrieved": retrieved_content}
    # TODO
    url = "https://us-central1-palisades-sec.cloudfunctions.net/palisade-feature"
    res = requests.post(
        url,
        data=json.dumps(body),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": cf_auth_token,
        },
    )
    # TODO Auth response handling
    if res.status_code == 401:
        raise Exception("Authorization for cloud function failed")
    response = json.loads(res.content)
    file_content = response["file_content"]
    file_path = response["file_path"]
    pr_data = response["pr_data"]
    return file_content, file_path, pr_data


def get_issues(repository_name, issue_number):
    url = f"https://api.github.com/repos/{repository_name}/issues/{issue_number}"
    res = requests.get(url, headers=headers)
    # TODO
    # if res.status_code == 200:
    # issues = json.loads(res.content)
    # issues = json.loads(res.content)
    # issue_class_list = []
    # for issue in issues:
    #     issue_class_list.append(GitHubIssue(**issue))
    # return issue_class_list
    issue = json.loads(res.content)
    return GitHubIssue(**issue)


def publish_changes(repository_name, file_content: str, file_path):
    #  Get main branch sha
    print("Get main branch sha")
    url = f"https://api.github.com/repos/{repository_name}/git/ref/heads/main"
    res = requests.get(url, headers=headers)
    print(res.content)
    sha = json.loads(res.content)["object"]["sha"]

    #  Create new branch
    print("Create new branch")
    new_branch_name = f"test_branch_{uuid4()}"
    url = f"https://api.github.com/repos/{repository_name}/git/refs"
    body = {"ref": f"refs/heads/{new_branch_name}", "sha": sha}
    res = requests.post(url, data=json.dumps(body), headers=headers)
    print(res.content)

    #  Get file SHA
    print("Get file SHA")
    url = f"https://api.github.com/repos/{repository_name}/contents/{file_path}"
    res = requests.get(url, headers=headers)
    print(res.content)
    sha = json.loads(res.content)["sha"]

    # Update file
    print("Update file")
    content = base64.b64encode(file_content.encode("ascii"))
    body = {
        "message": "commit from palisade",
        "content": content.decode("ascii"),
        "branch": new_branch_name,
        "sha": sha,
    }
    res = requests.put(url, data=json.dumps(body), headers=headers)
    print(res.content)
    return new_branch_name


def create_pr(repository_name, head, base, pr_data):
    url = f"https://api.github.com/repos/{repository_name}/pulls"
    request_body = {
        "title": pr_data["pr_title"],
        "body": pr_data["pr_body"],
        "head": head,
        "base": base,
    }
    res = requests.post(url, data=json.dumps(request_body), headers=headers)
    return res


def main(repo, issue, cf_auth):
    vector_db = create_vector_db(repository_name=repo)
    print("Creating Vector DB")
    issue_data = get_issues(repo, issue)
    file_content, file_path, pr_data = send_data(issue_data, vector_db, cf_auth)
    print(file_path)
    new_branch_name = publish_changes(repo, file_content, file_path)
    print("Create PR")
    create_pr(repo, new_branch_name, "main", pr_data)
    os.environ["CF_AUTH_TOKEN"] = cf_auth
    # feature_development_agent.run(
    #     f"{agent_prompt}\nNew Issues created:\nIssue number {issue}"
    # )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Python Command Line App")

    # Define command line arguments
    parser.add_argument(
        "--palisades_token",
        required=True,
        help="Palisades api token - get it from palisades.streamlit.io. Required only for private repositories",
    )
    parser.add_argument(
        "--github_token",
        required=False,
        help="Github token to create PRs | Required only for Private Repositories",
    )
    parser.add_argument(
        "--issue_number",
        required=True,
        help="Issue number for which feature dev to be done",
    )
    parser.add_argument(
        "--repo_name",
        required=True,
        help="Repository name for which feature dev to be done",
    )

    args = parser.parse_args()

    # Access the values of the command line arguments
    palisades_token = args.palisades_token
    github_token = args.github_token
    issue_number = args.issue_number
    repo_name = args.repo_name

    if github_token is not None:
        os.environ["GITHUB_TOKEN"] = github_token
    main(repo_name, issue_number, palisades_token)
