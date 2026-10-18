const base = "http://127.0.0.1:3055/api";

async function call(path, { method = "GET", token, body } = {}) {
  const headers = {};
  if (token) headers.authorization = `Bearer ${token}`;
  if (body) headers["content-type"] = "application/json";
  const response = await fetch(base + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  return {
    status: response.status,
    body: text ? JSON.parse(text) : null,
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
  console.log(`ok  ${message}`);
}

const login = async (username, password) => {
  const result = await call("/auth/login", {
    method: "POST",
    body: { username, password },
  });
  assert(result.status === 201, `login ${username}`);
  return result.body;
};

const admin = await login("admin", "AccountTest2026!");

const rejectedAdminCode = await call("/registration-codes", {
  method: "POST",
  token: admin.token,
  body: { label: "不应签发", days: 7, role: "ADMIN" },
});
assert(
  rejectedAdminCode.status === 400,
  "registration code rejects ADMIN role",
);

const issued = await call("/registration-codes", {
  method: "POST",
  token: admin.token,
  body: { label: "工程师注册", days: 7, role: "ENGINEER" },
});
assert(issued.status === 201, "engineer registration code issued");
assert(issued.body.role === "ENGINEER", "issued code carries ENGINEER role");

const listed = await call("/registration-codes", { token: admin.token });
assert(
  listed.body.items.some(
    (item) => item.role === "ENGINEER" && item.prefix === issued.body.prefix,
  ),
  "code list exposes role",
);

const verified = await call("/auth/registration/verify", {
  method: "POST",
  body: { code: issued.body.code },
});
assert(verified.status === 201, "registration code verifies");
assert(verified.body.role === "ENGINEER", "verify reports ENGINEER role");

const shortPassword = await call("/auth/register", {
  method: "POST",
  body: {
    code: issued.body.code,
    name: "短密码",
    username: "shortpass",
    password: "seven77",
  },
});
assert(shortPassword.status === 400, "7-character password rejected");

const registered = await call("/auth/register", {
  method: "POST",
  body: {
    code: issued.body.code,
    name: "工程师甲",
    username: "engineer-a",
    password: "eight888",
  },
});
assert(registered.status === 201, "engineer registers with 8-character password");
assert(registered.body.user.role === "ENGINEER", "registered role is ENGINEER");

const reused = await call("/auth/register", {
  method: "POST",
  body: {
    code: issued.body.code,
    name: "重复",
    username: "engineer-b",
    password: "eight888",
  },
});
assert(reused.status === 400, "registration code cannot be reused");

const engineer = await login("engineer-a", "eight888");
const usersAsEngineer = await call("/users", { token: engineer.token });
assert(usersAsEngineer.status === 403, "engineer cannot list accounts");
const codesAsEngineer = await call("/registration-codes", {
  token: engineer.token,
});
assert(codesAsEngineer.status === 403, "engineer cannot issue codes");

const createdAdmin = await call("/users", {
  method: "POST",
  token: admin.token,
  body: {
    name: "管理员乙",
    username: "admin-b",
    password: "adminpas8",
    role: "ADMIN",
  },
});
assert(createdAdmin.status === 201, "admin creates another admin directly");
assert(createdAdmin.body.role === "ADMIN", "created account keeps ADMIN role");

const adminB = await login("admin-b", "adminpas8");
const usersAsAdminB = await call("/users", { token: adminB.token });
assert(usersAsAdminB.status === 200, "new admin can list accounts");

console.log("all account and registration checks passed");
