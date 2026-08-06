// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @notice Minimal ERC-5484 interface used by the HALAH proof of concept.
interface IERC5484 {
    enum BurnAuth {
        IssuerOnly,
        OwnerOnly,
        Both,
        Neither
    }

    event Issued(
        address indexed from,
        address indexed to,
        uint256 indexed tokenId,
        BurnAuth burnAuth
    );

    function burnAuth(uint256 tokenId) external view returns (BurnAuth);
}

/// @title HALAH Consent Soulbound Token
/// @notice Local blockchain proof of concept for multi-party and time-bound patient consent.
contract ConsentSBT is ERC721, Ownable, IERC5484 {
    uint256 private _nextTokenId;

    struct Consent {
        address patient;
        address requester;
        bytes32 consentHash;
        bytes32 approvalHash;
        string purpose;
        uint64 validFrom;
        uint64 validUntil;
        uint16 threshold;
        uint16 approvalCount;
        bool revoked;
    }

    mapping(uint256 => Consent) public consents;
    mapping(bytes32 => uint256) public tokenByConsentHash;
    mapping(uint256 => BurnAuth) private _burnAuthorizations;

    event ConsentIssued(
        uint256 indexed tokenId,
        bytes32 indexed consentHash,
        bytes32 indexed approvalHash,
        address patient,
        address requester,
        uint64 validFrom,
        uint64 validUntil,
        uint16 threshold,
        uint16 approvalCount
    );

    event ConsentRevoked(
        uint256 indexed tokenId,
        bytes32 indexed consentHash,
        uint256 revokedAt
    );

    constructor() ERC721("HALAH Medical Consent", "HALAH-CONSENT") {}

    /// @notice Mints one non-transferable consent token after the off-chain threshold is met.
    function mintConsent(
        address patient,
        address requester,
        bytes32 consentHash,
        bytes32 approvalHash,
        string calldata purpose,
        uint64 validFrom,
        uint64 validUntil,
        uint16 threshold,
        uint16 approvalCount
    ) external onlyOwner returns (uint256 tokenId) {
        require(patient != address(0), "Invalid patient");
        require(requester != address(0), "Invalid requester");
        require(consentHash != bytes32(0), "Invalid consent hash");
        require(approvalHash != bytes32(0), "Invalid approval hash");
        require(validUntil > validFrom, "Invalid validity window");
        require(threshold >= 2, "Threshold must be at least two");
        require(approvalCount >= threshold, "Insufficient approvals");
        require(tokenByConsentHash[consentHash] == 0, "Consent already minted");

        tokenId = ++_nextTokenId;
        _safeMint(patient, tokenId);

        consents[tokenId] = Consent({
            patient: patient,
            requester: requester,
            consentHash: consentHash,
            approvalHash: approvalHash,
            purpose: purpose,
            validFrom: validFrom,
            validUntil: validUntil,
            threshold: threshold,
            approvalCount: approvalCount,
            revoked: false
        });
        tokenByConsentHash[consentHash] = tokenId;
        _burnAuthorizations[tokenId] = BurnAuth.IssuerOnly;

        emit Issued(address(0), patient, tokenId, BurnAuth.IssuerOnly);
        emit ConsentIssued(
            tokenId,
            consentHash,
            approvalHash,
            patient,
            requester,
            validFrom,
            validUntil,
            threshold,
            approvalCount
        );
    }

    /// @notice Revokes access while preserving the SBT and its audit history.
    function revoke(uint256 tokenId) external onlyOwner {
        require(_exists(tokenId), "Unknown token");
        Consent storage consent = consents[tokenId];
        require(!consent.revoked, "Already revoked");
        consent.revoked = true;
        emit ConsentRevoked(tokenId, consent.consentHash, block.timestamp);
    }

    function checkValid(uint256 tokenId) public view returns (bool) {
        if (!_exists(tokenId)) return false;
        Consent memory consent = consents[tokenId];
        return
            !consent.revoked &&
            block.timestamp >= consent.validFrom &&
            block.timestamp <= consent.validUntil;
    }

    function checkAccess(uint256 tokenId, address requester)
        external
        view
        returns (bool)
    {
        return checkValid(tokenId) && consents[tokenId].requester == requester;
    }

    function burnAuth(uint256 tokenId)
        external
        view
        override
        returns (BurnAuth)
    {
        require(_exists(tokenId), "Unknown token");
        return _burnAuthorizations[tokenId];
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721)
        returns (bool)
    {
        return
            interfaceId == type(IERC5484).interfaceId ||
            super.supportsInterface(interfaceId);
    }

    /// @dev ERC-721 approvals have no meaning for a soulbound token.
    function approve(address, uint256) public pure override {
        revert("Soulbound token");
    }

    function setApprovalForAll(address, bool) public pure override {
        revert("Soulbound token");
    }

    /// @dev Minting and burning are permitted; wallet-to-wallet transfers are forbidden.
    function _beforeTokenTransfer(
        address from,
        address to,
        uint256 firstTokenId,
        uint256 batchSize
    ) internal override {
        require(from == address(0) || to == address(0), "Soulbound token");
        super._beforeTokenTransfer(from, to, firstTokenId, batchSize);
    }
}
